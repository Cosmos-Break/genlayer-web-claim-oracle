import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createAccount, createClient, generatePrivateKey, isSuccessful } from "genlayer-js";
import { studionet, testnetBradbury } from "genlayer-js/chains";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONTRACT_PATH = path.resolve(__dirname, "../contracts/web_claim_oracle.py");

function loadDotEnv() {
  const envPath = path.resolve(__dirname, "../.env");
  if (!fs.existsSync(envPath)) return;
  for (const raw of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const idx = line.indexOf("=");
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim().replace(/^['"]|['"]$/g, "");
    if (key && !(key in process.env)) process.env[key] = val;
  }
}

async function fundStudioAccount(address) {
  const res = await fetch("https://studio.genlayer.com/api", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "sim_fundAccount",
      params: [address, 1000],
    }),
  });
  return res.json();
}

async function main() {
  loadDotEnv();
  const target = process.argv.includes("--bradbury") ? "bradbury" : "studionet";
  const chain = target === "bradbury" ? testnetBradbury : studionet;

  let privateKey = process.env.GENLAYER_PRIVATE_KEY?.trim();
  if (!privateKey) {
    if (target === "bradbury") {
      throw new Error("GENLAYER_PRIVATE_KEY is required for --bradbury.");
    }
    privateKey = generatePrivateKey();
    console.log("Generated ephemeral Studionet testnet account for this run.");
  }

  const account = createAccount(privateKey);
  const client = createClient({ chain, account });

  console.log(`=== GenLayer WebClaimOracle Deploy & Verify (${target}) ===`);
  console.log(`Wallet: ${account.address}`);
  console.log(`Chain:  ${chain.name} (id=${chain.id})`);

  if (target === "studionet") {
    const fundRes = await fundStudioAccount(account.address);
    console.log("1. Studio faucet sim_fundAccount:", JSON.stringify(fundRes));
  }

  const code = fs.readFileSync(CONTRACT_PATH, "utf8");
  const schema = await client.getContractSchemaForCode(code);
  console.log("2. Validated contract schema methods:", Object.keys(schema?.methods || {}));

  const deployFees = await client.estimateTransactionFees();
  const deployTxHash = await client.deployContract({
    code,
    args: [],
    leaderOnly: false,
    fees: {
      distribution: deployFees.distribution,
      feeValue: deployFees.feeValue,
    },
  });
  console.log(`   deployTxHash: ${deployTxHash}`);

  const deployReceipt = await client.waitForTransactionReceipt({
    hash: deployTxHash,
    waitUntil: "decided",
    retries: 60,
    interval: 3000,
  });

  const contractAddress =
    deployReceipt?.data?.contract_address ||
    deployReceipt?.contract_address ||
    deployReceipt?.to_address;

  if (!contractAddress || !isSuccessful(deployReceipt)) {
    throw new Error(`Deployment failed: ${JSON.stringify(deployReceipt).slice(0, 800)}`);
  }
  console.log(`   Deployed contractAddress: ${contractAddress}`);

  const claimId = `verify-genlayer-networks-${Date.now()}`;
  const sourceUrl = "https://docs.genlayer.com/developers/networks.md";
  const statement = "GenLayer documentation lists Testnet Bradbury as an official GenLayer network.";

  console.log(`3. Submitting live AI-adjudicated claim (${claimId})...`);
  const writeFees = await client.estimateTransactionFeesForWrite({
    address: contractAddress,
    functionName: "submit_claim",
    args: [claimId, sourceUrl, statement],
    leaderOnly: false,
  });
  const writeTxHash = await client.writeContract({
    address: contractAddress,
    functionName: "submit_claim",
    args: [claimId, sourceUrl, statement],
    leaderOnly: false,
    fees: {
      distribution: writeFees.distribution,
      feeValue: writeFees.feeValue,
    },
  });
  console.log(`   writeTxHash: ${writeTxHash}`);

  const writeReceipt = await client.waitForTransactionReceipt({
    hash: writeTxHash,
    waitUntil: "decided",
    retries: 60,
    interval: 4000,
  });
  if (!isSuccessful(writeReceipt)) {
    throw new Error(`submit_claim failed: ${JSON.stringify(writeReceipt).slice(0, 1200)}`);
  }

  const storedClaim = await client.readContract({
    address: contractAddress,
    functionName: "get_claim",
    args: [claimId],
  });
  const stats = await client.readContract({
    address: contractAddress,
    functionName: "get_stats",
    args: [],
  });
  console.log("4. Verified on-chain state:");
  console.log("   get_claim:", storedClaim);
  console.log("   get_stats:", JSON.stringify(stats));
}

main().catch((err) => {
  console.error("ERROR:", err?.message || err);
  process.exit(1);
});
