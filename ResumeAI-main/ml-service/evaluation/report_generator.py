import json
import os
from typing import Dict, List

def generate_reports(results: List[Dict], output_dir: str):
    """Generates machine-readable JSON and readable Markdown summary reports."""
    os.makedirs(output_dir, exist_ok=True)

    json_report_path = os.path.join(output_dir, "evaluation_report.json")
    md_report_path = os.path.join(output_dir, "rag_eval_summary.md")

    # Save JSON report
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Calculate averages
    num_examples = len(results)
    
    avg_latency_non_rag = sum(r["non_rag"]["latency_ms"] for r in results) / num_examples
    avg_latency_rag = sum(r["rag"]["latency_ms"] for r in results) / num_examples
    avg_retrieval_precision = sum(r["rag"]["retrieval_precision_at_k"] for r in results) / num_examples
    avg_grounded_rate = sum(r["rag"]["grounded_recommendation_rate"] for r in results) / num_examples
    avg_unsupported_rate = sum(r["rag"]["unsupported_claim_rate"] for r in results) / num_examples
    avg_source_attribution = sum(r["rag"]["source_attribution_coverage"] for r in results) / num_examples

    def avg_judge_score(run_type, metric):
        return sum(r[run_type]["judge_scores"].get(metric, 0) for r in results) / num_examples

    metrics = ["relevance", "actionability", "role_specificity", "factual_grounding", "clarity"]
    
    # Save Markdown report
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write("# RAG Evaluation Summary\n\n")
        
        f.write("## Overview\n")
        f.write(f"Evaluated {num_examples} synthetic resume/JD pairs across various roles.\n\n")

        f.write("## Objective Metrics\n")
        f.write(f"- **Retrieval Precision at K**: {avg_retrieval_precision:.2f}\n")
        f.write(f"- **Grounded Recommendation Rate**: {avg_grounded_rate:.2f}\n")
        f.write(f"- **Unsupported Claim Rate**: {avg_unsupported_rate:.2f}\n")
        f.write(f"- **Source Attribution Coverage**: {avg_source_attribution:.2f}\n")
        f.write(f"- **Latency (Non-RAG)**: {avg_latency_non_rag:.0f} ms\n")
        f.write(f"- **Latency (RAG)**: {avg_latency_rag:.0f} ms\n\n")

        f.write("## Subjective Quality (LLM Judge 1-5 Scale)\n")
        f.write("| Metric | Non-RAG | RAG |\n")
        f.write("|--------|---------|-----|\n")
        for m in metrics:
            f.write(f"| {m.capitalize()} | {avg_judge_score('non_rag', m):.2f} | {avg_judge_score('rag', m):.2f} |\n")
        
        f.write("\n## Recommendation\n")
        
        # Determine if RAG should be enabled by default
        rag_score_total = sum(avg_judge_score('rag', m) for m in metrics)
        non_rag_score_total = sum(avg_judge_score('non_rag', m) for m in metrics)
        
        if rag_score_total > non_rag_score_total and avg_grounded_rate > 0.5 and avg_unsupported_rate < 0.2:
            f.write("**Conclusion**: RAG demonstrates a measurable improvement in feedback quality and grounding. Enabling RAG by default is justified.\n")
        else:
            f.write("**Conclusion**: RAG does not yet show sufficient improvement or has high hallucination rates. Do not enable by default until further tuning.\n")

    return json_report_path, md_report_path
