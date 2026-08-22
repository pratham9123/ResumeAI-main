import os
import sys
import logging
from dotenv import load_dotenv

# Ensure ml-service is in the Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
ml_service_dir = os.path.join(os.path.dirname(current_dir), "ml-service")
sys.path.insert(0, ml_service_dir)

load_dotenv(os.path.join(ml_service_dir, ".env"))

from evaluation.rag_evaluator import run_evaluation
from evaluation.report_generator import generate_reports

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    dataset_path = os.path.join(ml_service_dir, "evaluation", "dataset.json")
    output_dir = os.path.join(ml_service_dir, "evaluation_reports")
    
    logger.info(f"Starting RAG evaluation using dataset: {dataset_path}")
    
    try:
        results, _ = run_evaluation(dataset_path)
        logger.info("Evaluation runs completed successfully. Generating reports...")
        
        json_report, md_report = generate_reports(results, output_dir)
        
        logger.info(f"Reports generated successfully:")
        logger.info(f"  JSON Report: {json_report}")
        logger.info(f"  Markdown Summary: {md_report}")
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
