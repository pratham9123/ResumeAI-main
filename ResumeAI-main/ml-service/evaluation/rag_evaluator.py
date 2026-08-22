import json
import logging
import os
import time
from typing import Dict, List, Tuple
from google import genai
from google.genai import types

from modules.analysis_pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

# LLM Judge Prompt Template
JUDGE_PROMPT = """
You are an expert ATS (Applicant Tracking System) consultant and career coach evaluator.
Your task is to evaluate the quality of resume feedback provided by an AI system.

Evaluate the following AI feedback based on these criteria on a scale of 1 to 5 (1=Poor, 5=Excellent):
1. Relevance (Is the feedback relevant to the user's resume and job description?)
2. Actionability (Are the suggestions practical and easy to implement immediately?)
3. Role Specificity (Does the feedback align specifically with the target role requirements?)
4. Factual Grounding (Are the recommendations grounded in the provided resume context and retrieved data, avoiding hallucinations?)
5. Clarity (Is the feedback easy to understand and well-structured?)

Provide your response in strict JSON format:
{
    "relevance": <int>,
    "actionability": <int>,
    "role_specificity": <int>,
    "factual_grounding": <int>,
    "clarity": <int>
}

Resume Text:
{resume_text}

Job Description:
{job_description}

Target Role:
{target_role}

AI Feedback to Evaluate:
{feedback}
"""

def evaluate_subjective_quality(
    resume_text: str,
    job_description: str,
    target_role: str,
    feedback: Dict,
    api_key: str,
) -> Dict:
    """Uses Gemini as a judge to evaluate the subjective quality of the feedback."""
    try:
        client = genai.Client(api_key=api_key)
        prompt = JUDGE_PROMPT.format(
            resume_text=resume_text,
            job_description=job_description,
            target_role=target_role,
            feedback=json.dumps(feedback, indent=2)
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Failed to evaluate subjective quality: {e}")
        return {
            "relevance": 0,
            "actionability": 0,
            "role_specificity": 0,
            "factual_grounding": 0,
            "clarity": 0
        }

def run_evaluation(dataset_path: str) -> Tuple[List[Dict], List[Dict]]:
    """Runs the evaluation on the provided dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    gemini_key = os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("GOOGLE_GEMINI_API_KEY is not set.")

    results = []
    
    for idx, item in enumerate(dataset):
        logger.info(f"Evaluating example {idx + 1}/{len(dataset)} for role: {item['target_role']}")
        
        # Non-RAG Run
        start_time_non_rag = time.perf_counter()
        res_non_rag = run_analysis_pipeline(
            resume_text=item["resume_text"],
            job_description=item["job_description"],
            pdf_bytes=None,
            target_role=item["target_role"],
            rag_enabled=False
        )
        latency_non_rag = round((time.perf_counter() - start_time_non_rag) * 1000)

        # RAG Run
        start_time_rag = time.perf_counter()
        res_rag = run_analysis_pipeline(
            resume_text=item["resume_text"],
            job_description=item["job_description"],
            pdf_bytes=None,
            target_role=item["target_role"],
            rag_enabled=True
        )
        latency_rag = round((time.perf_counter() - start_time_rag) * 1000)

        # Calculate Objective Metrics
        retrieved_guidance = res_rag.get("rag", {}).get("retrieved_guidance", [])
        retrieval_count = res_rag.get("rag", {}).get("retrieval_metadata", {}).get("count", 0)
        retrieval_precision = 0.0
        
        if retrieval_count > 0:
            relevant_hits = sum(
                1 for doc in retrieved_guidance 
                if doc.get("category") in item["expected_relevant_categories"]
            )
            retrieval_precision = relevant_hits / retrieval_count
        
        # Grounded rate and unsupported claim checks
        feedback_str_rag = json.dumps(res_rag.get("feedback", {}))
        grounded_rate = 1.0 if res_rag.get("feedback", {}).get("source_ids") else 0.0
        
        unsupported_claims_found = 0
        for prohibited in item["prohibited_fabricated_claims"]:
            if prohibited.lower() in feedback_str_rag.lower():
                unsupported_claims_found = 1
                break
        
        # Subjective Quality Evaluation via LLM Judge
        judge_scores_non_rag = evaluate_subjective_quality(
            item["resume_text"], item["job_description"], item["target_role"], res_non_rag.get("feedback", {}), gemini_key
        )
        judge_scores_rag = evaluate_subjective_quality(
            item["resume_text"], item["job_description"], item["target_role"], res_rag.get("feedback", {}), gemini_key
        )

        results.append({
            "target_role": item["target_role"],
            "non_rag": {
                "latency_ms": latency_non_rag,
                "judge_scores": judge_scores_non_rag
            },
            "rag": {
                "latency_ms": latency_rag,
                "retrieval_precision_at_k": retrieval_precision,
                "grounded_recommendation_rate": grounded_rate,
                "unsupported_claim_rate": unsupported_claims_found,
                "source_attribution_coverage": len(res_rag.get("feedback", {}).get("source_ids", [])) / max(retrieval_count, 1),
                "judge_scores": judge_scores_rag,
                "token_usage": res_rag.get("rag", {}).get("retrieval_metadata", {}).get("count", 0) * 100 # Rough estimate if actual not exposed
            }
        })

    return results, dataset
