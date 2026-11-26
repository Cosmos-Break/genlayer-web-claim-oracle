# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class WebClaimOracle(gl.Contract):
    """
    AI-adjudicated Web Claim Oracle on GenLayer.

    Fetches a live public URL inside a non-deterministic block, asks an LLM to
    verify a factual statement against the retrieved content using a strict JSON
    schema, and reaches validator consensus by verifying both JSON structure and
    independent verdict agreement (SUPPORTED / REFUTED / INSUFFICIENT).
    """

    owner: Address
    claim_ids: DynArray[str]
    claims_json: TreeMap[str, str]
    total_claims: u256
    supported_count: u256
    refuted_count: u256
    insufficient_count: u256

    def __init__(self):
        self.owner = gl.message.sender_address
        self.total_claims = u256(0)
        self.supported_count = u256(0)
        self.refuted_count = u256(0)
        self.insufficient_count = u256(0)

    @gl.public.write
    def submit_claim(self, claim_id: str, source_url: str, statement: str) -> str:
        clean_id = claim_id.strip()
        if len(clean_id) == 0 or len(clean_id) > 64:
            raise gl.vm.UserError("claim_id must be 1..64 characters")
        if clean_id in self.claims_json:
            raise gl.vm.UserError(f"claim_id already adjudicated: {clean_id}")
        if not (source_url.startswith("https://") or source_url.startswith("http://")):
            raise gl.vm.UserError("source_url must start with http:// or https://")
        if len(statement.strip()) == 0 or len(statement) > 512:
            raise gl.vm.UserError("statement must be 1..512 characters")

        def evaluate() -> dict:
            resp = gl.nondet.web.get(
                source_url,
                headers={"User-Agent": "genlayer-web-claim-oracle/1.0"},
            )
            status_code = getattr(resp, "status", getattr(resp, "status_code", 200))
            if status_code >= 400:
                raise gl.vm.UserError(f"source_url returned HTTP {status_code}")
            raw_body = resp.body
            raw_text = (
                raw_body.decode("utf-8", errors="ignore")
                if isinstance(raw_body, (bytes, bytearray))
                else str(raw_body or "")
            )
            # Cap excerpt to keep validator prompt cost bounded and deterministic
            excerpt = raw_text[:6000]
            prompt = (
                "You are an objective fact-checking oracle. Evaluate whether the "
                "STATEMENT is supported by the SOURCE_CONTENT.\n"
                "Respond ONLY with a JSON object containing exactly these keys:\n"
                '- "verdict": one of "SUPPORTED", "REFUTED", or "INSUFFICIENT"\n'
                '- "confidence": integer from 0 to 100\n'
                '- "evidence": one concise sentence (max 160 chars) quoting or summarizing the key evidence\n\n'
                f"STATEMENT:\n{statement}\n\n"
                f"SOURCE_URL:\n{source_url}\n\n"
                f"SOURCE_CONTENT:\n{excerpt}\n"
            )
            result = gl.nondet.exec_prompt(prompt, response_format="json")
            if isinstance(result, str):
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`")
                    if cleaned.lower().startswith("json"):
                        cleaned = cleaned[4:].strip()
                result = json.loads(cleaned)
            verdict = str(result.get("verdict", "")).strip().upper()
            confidence = max(0, min(100, int(float(result.get("confidence", 0)))))
            evidence = str(result.get("evidence", "")).strip()[:200]
            return {
                "verdict": verdict,
                "confidence": confidence,
                "evidence": evidence,
            }

        def validate(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            data = leader_result.calldata
            if not isinstance(data, dict):
                return False
            verdict = data.get("verdict")
            confidence = data.get("confidence")
            evidence = data.get("evidence")
            if verdict not in ("SUPPORTED", "REFUTED", "INSUFFICIENT"):
                return False
            if not isinstance(confidence, int) or confidence < 0 or confidence > 100:
                return False
            if not isinstance(evidence, str) or len(evidence.strip()) == 0:
                return False
            # Validator independently evaluates and requires verdict agreement
            own = evaluate()
            return own.get("verdict") == verdict

        adjudicated = gl.vm.run_nondet_unsafe(evaluate, validate)

        record = {
            "claim_id": clean_id,
            "source_url": source_url,
            "statement": statement,
            "verdict": adjudicated["verdict"],
            "confidence": adjudicated["confidence"],
            "evidence": adjudicated["evidence"],
            "submitter": str(gl.message.sender_address),
        }
        serialized = json.dumps(record, sort_keys=True)
        self.claim_ids.append(clean_id)
        self.claims_json[clean_id] = serialized
        self.total_claims = self.total_claims + u256(1)

        if adjudicated["verdict"] == "SUPPORTED":
            self.supported_count = self.supported_count + u256(1)
        elif adjudicated["verdict"] == "REFUTED":
            self.refuted_count = self.refuted_count + u256(1)
        else:
            self.insufficient_count = self.insufficient_count + u256(1)

        return serialized

    @gl.public.view
    def get_claim(self, claim_id: str) -> str:
        if claim_id not in self.claims_json:
            return ""
        return self.claims_json[claim_id]

    @gl.public.view
    def list_claim_ids(self) -> list[str]:
        return [cid for cid in self.claim_ids]

    @gl.public.view
    def get_stats(self) -> dict[str, str]:
        return {
            "owner": str(self.owner),
            "total_claims": str(self.total_claims),
            "supported": str(self.supported_count),
            "refuted": str(self.refuted_count),
            "insufficient": str(self.insufficient_count),
        }
