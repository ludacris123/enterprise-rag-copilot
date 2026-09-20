import asyncio
import json
from pathlib import Path
from app.ingestion import ingest
from app.service import answer

async def main() -> dict:
    ingest("Employee Travel Policy", "Employees must claim domestic travel expenses within 30 days. Claims above INR 25000 require manager approval.", "demo-tenant", {"department": "finance"})
    ingest("Security Handbook", "Never share passwords, OTPs, recovery codes, or complete card numbers.", "demo-tenant", {"department": "security"})
    cases = [json.loads(line) for line in Path(__file__).with_name("golden.jsonl").read_text().splitlines() if line]
    results = []
    for case in cases:
        output = await answer(case["question"], "demo-tenant", {"department": case["department"]})
        term_ok = all(term.lower() in output.answer.lower() for term in case["expected_terms"])
        citation_ok = case["should_refuse"] or bool(output.citations)
        results.append({"id": case["id"], "passed": term_ok and citation_ok, "grounded": output.grounded})
    passed = sum(item["passed"] for item in results)
    report = {"total": len(results), "passed": passed, "pass_rate": passed / len(results), "details": results}
    print(json.dumps(report, indent=2))
    if passed != len(results):
        raise SystemExit(1)
    return report

if __name__ == "__main__":
    asyncio.run(main())
