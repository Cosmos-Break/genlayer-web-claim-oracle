# WebClaimOracle — AI-Adjudicated Fact Verification on GenLayer

**WebClaimOracle** is a GenLayer Intelligent Contract written in Python that fetches live public web sources inside non-deterministic execution blocks, uses an LLM with strict JSON output to adjudicate factual claims (`SUPPORTED` / `REFUTED` / `INSUFFICIENT`), and reaches decentralized validator consensus via the GenLayer Equivalence Principle (`gl.vm.run_nondet_unsafe`).

## Why GenLayer?

Traditional EVM smart contracts cannot read arbitrary live web URLs or evaluate natural-language statements against unstructured web documents without trusting a centralized off-chain oracle. `WebClaimOracle` demonstrates GenLayer's core capabilities:

- **Native Web Access (`gl.nondet.web.get`)**: Fetches live public URLs directly inside the GenVM execution environment with HTTP error handling.
- **Structured LLM Reasoning (`gl.nondet.exec_prompt(..., response_format="json")`)**: Evaluates whether a submitted factual statement is supported by the fetched source content, returning `{verdict, confidence, evidence}`.
- **Custom Equivalence Principle Validator (`gl.vm.run_nondet_unsafe`)**: Because LLM phrasing and confidence scores are non-deterministic across validators, each validator independently checks the leader's JSON schema/bounds and runs its own web fetch + LLM evaluation, reaching consensus on **verdict agreement** rather than brittle exact string equality.
- **On-Chain Audit Trail**: Stores every adjudicated claim record in `TreeMap[str, str]` + `DynArray[str]` along with cumulative verdict counters (`total_claims`, `supported`, `refuted`, `insufficient`).

## Contract Overview

Source: [`contracts/web_claim_oracle.py`](contracts/web_claim_oracle.py)

| Method | Kind | Description |
|---|---|---|
| `submit_claim(claim_id, source_url, statement)` | `@gl.public.write` | Validates inputs, fetches `source_url`, adjudicates `statement` via LLM + validator consensus, and stores the immutable JSON record on-chain. |
| `get_claim(claim_id)` | `@gl.public.view` | Returns the settled JSON record for a given `claim_id` (or `""` if not found). |
| `list_claim_ids()` | `@gl.public.view` | Returns all adjudicated `claim_id` keys in submission order. |
| `get_stats()` | `@gl.public.view` | Returns contract `owner` and cumulative verdict counters (`total_claims`, `supported`, `refuted`, `insufficient`). |

## Live Verified Deployment (GenLayer Studionet)

Deployed and verified end-to-end on **GenLayer Studionet (Chain ID `61999`)** using `genlayer-js@2.1.0`:

- **Contract Address**: `0x2A9D825208aa098d210a8E3BEEE3E24Dff97eBED`
- **Deployer Address**: `0x49A4A1299bf967f83E8964F816E7c830814B0B90`
- **Deploy Tx Hash**: `0x6ccceb6ce12b0379e03d1f23e8e259d1035cb6fb34c5685decf4173f3cdb36f8` (`ACCEPTED`)
- **Live Adjudicated Claim #1**:
  - Tx Hash: `0x72d3d6c296d5b6483c4cd9678796f83ff7c61145a478735e762ac5b7e7e7e07e` (`ACCEPTED`)
  - Source: `https://docs.genlayer.com/developers/networks.md`
  - Statement: *"GenLayer documentation lists Testnet Bradbury as an official GenLayer network."*
  - Settled Verdict: `SUPPORTED` (`confidence: 100`)
- **Live Adjudicated Claim #2**:
  - Tx Hash: `0xae040159760356b2ade9c85aaeead1550763f8550760d034c7721b5313bbd3e2` (`ACCEPTED`)
  - Source: `https://docs.genlayer.com/developers/intelligent-contracts/first-contract.md`
  - Statement: *"GenLayer Intelligent Contracts are written in Python and inherit from gl.Contract."*
  - Settled Verdict: `SUPPORTED` (`confidence: 99`)

## Quickstart

### Prerequisites
- Node.js `>= 20`
- A dedicated testnet EVM private key (never use a wallet holding mainnet funds)

### Install & Run on Studionet (Free Built-in Faucet)

```bash
npm install
cp .env.example .env
# Edit .env and set GENLAYER_PRIVATE_KEY=0x... (or omit to auto-generate an ephemeral testnet key)
npm run deploy:studio
```

### Deploy to Testnet Bradbury

If your testnet account holds Bradbury `GEN` test tokens:

```bash
npm run deploy:bradbury
```

## License

MIT
