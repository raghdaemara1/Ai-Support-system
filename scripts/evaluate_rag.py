import sys
import os
import argparse
from typing import List, Dict

# Add the project root to the python path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.vectorstore import get_vectorstore


# Golden Dataset for Evaluation (Example)
# In a real enterprise system, this is curated by experts (100+ Q&A pairs)
EVAL_DATASET = [
    {
        "question": "What does alarm code 2008 mean?",
        "expected_keywords": ["Process parameter tolerance limit undershot", "temperature"],
    },
    {
        "question": "How do I fix a mechanical jam?",
        "expected_keywords": ["jam", "mechanical", "clear", "obstruction"],
    },
    {
        "question": "What is the reason for a Sensor/Instrumentation fault?",
        "expected_keywords": ["sensor", "instrumentation", "limit switch", "encoder"],
    },
]


def evaluate_retrieval(tenant_id: str, k: int = 3) -> Dict[str, float]:
    """
    Evaluate the RAG Retrieval pipeline using a golden dataset.
    
    Metrics:
    - Recall@K: What percentage of queries successfully retrieved a chunk 
                containing the expected keywords in the top K results?
    """
    print(f"\n🚀 Running RAG Retrieval Evaluation (k={k}) for tenant '{tenant_id}'...")
    
    try:
        vectorstore = get_vectorstore(tenant_id)
    except Exception as e:
        print(f"❌ Failed to connect to ChromaDB: {e}")
        return {"recall@k": 0.0}

    success_count = 0
    total_queries = len(EVAL_DATASET)

    for item in EVAL_DATASET:
        question = item["question"]
        expected_keywords = item["expected_keywords"]
        
        print(f"\nQuery: '{question}'")
        
        try:
            # Retrieve top K documents
            results = vectorstore.similarity_search(question, k=k)
            retrieved_text = " ".join([doc.page_content.lower() for doc in results])
            
            # Check if ANY of the expected keywords were found in the retrieved chunks
            # In a strict eval, you might require ALL keywords. We use ANY for a basic check.
            found = any(keyword.lower() in retrieved_text for keyword in expected_keywords)
            
            if found:
                print("✅ PASS: Relevant context retrieved.")
                success_count += 1
            else:
                print("❌ FAIL: Expected keywords missing from top-K chunks.")
                
        except Exception as e:
            print(f"⚠️ Error during retrieval: {e}")

    recall_at_k = (success_count / total_queries) * 100 if total_queries > 0 else 0.0
    
    print("\n" + "="*40)
    print(f"📊 EVALUATION RESULTS")
    print("="*40)
    print(f"Total Queries Tested : {total_queries}")
    print(f"Successful Retrievals: {success_count}")
    print(f"Recall@{k}             : {recall_at_k:.2f}%")
    print("="*40)
    
    # Enterprise FDE Note: 
    # If Recall@K drops below 85%, we need to tune chunk_size, adjust embedding models, 
    # or implement Hybrid Search (BM25 + Dense).
    return {"recall@k": recall_at_k}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate RAG Retrieval Recall")
    parser.add_argument("--tenant", type=str, default="obeikan", help="Tenant ID to evaluate against")
    parser.add_argument("--k", type=int, default=3, help="Number of chunks to retrieve (Top-K)")
    
    args = parser.parse_args()
    evaluate_retrieval(tenant_id=args.tenant, k=args.k)
