"""
AI Insights Generation using Groq (Llama 3.3)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import httpx
import os
import json
from src.api.database import get_db_connection

router = APIRouter(prefix="/insights", tags=["insights"])

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

class InsightRequest(BaseModel):
    include_network_summary: bool = True
    include_routes: bool = True
    include_operators: bool = True
    include_trends: bool = True
    include_worst_routes: bool = True
    include_best_routes: bool = True


class InsightResponse(BaseModel):
    executive_summary: str
    key_findings: List[str]
    critical_issues: List[dict]
    opportunities: List[dict]
    recommendations: List[dict]
    generated_at: str
    data_period: str


def get_network_data(year: int, month: int) -> dict:
    """Fetch network SRI data"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                network_sri_score,
                network_grade,
                total_routes,
                routes_grade_a,
                routes_grade_b,
                routes_grade_c,
                routes_grade_d,
                routes_grade_f,
                avg_headway_score,
                avg_schedule_score,
                avg_journey_time_score,
                avg_service_delivery_score
            FROM network_reliability_index
            WHERE year = %s AND month = %s
                AND day_of_week IS NULL AND hour IS NULL
            LIMIT 1
        """, (year, month))
        
        result = cur.fetchone()
        return dict(result) if result else {}
    finally:
        cur.close()
        conn.close()


def get_routes_data(year: int, month: int, limit: int = 100) -> List[dict]:
    """Fetch route-level SRI data"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                route_name,
                direction,
                operator,
                sri_score,
                sri_grade,
                headway_consistency_score,
                schedule_adherence_score,
                journey_time_consistency_score,
                service_delivery_score,
                data_completeness
            FROM service_reliability_index
            WHERE year = %s AND month = %s
                AND day_of_week IS NULL AND hour IS NULL
            ORDER BY sri_score ASC
            LIMIT %s
        """, (year, month, limit))
        
        results = cur.fetchall()
        return [dict(r) for r in results]
    finally:
        cur.close()
        conn.close()


def get_operators_data(year: int, month: int) -> List[dict]:
    """Fetch operator summary data"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            WITH normalized AS (
                SELECT 
                    CASE 
                        WHEN operator IN ('Arriva Merseyside', 'Arriva Northwest', 'Arriva North West') THEN 'Arriva'
                        WHEN operator IN ('Stagecoach Merseyside', 'Stagecoach Merseyside and South Lancashire') THEN 'Stagecoach'
                        ELSE operator
                    END as operator,
                    sri_score,
                    sri_grade
                FROM service_reliability_index
                WHERE year = %s AND month = %s
                    AND day_of_week IS NULL AND hour IS NULL
            )
            SELECT 
                operator,
                COUNT(*) as route_count,
                ROUND(AVG(sri_score)::numeric, 1) as avg_sri,
                COUNT(*) FILTER (WHERE sri_grade = 'F') as failing_routes
            FROM normalized
            GROUP BY operator
            ORDER BY avg_sri DESC
        """, (year, month))
        
        results = cur.fetchall()
        return [dict(r) for r in results]
    finally:
        cur.close()
        conn.close()


def get_trends_data(year: int, month: int) -> dict:
    """Fetch hourly and daily trends"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Hourly patterns
        cur.execute("""
            SELECT hour, ROUND(AVG(network_sri_score)::numeric, 1) as sri
            FROM network_reliability_index
            WHERE year = %s AND month = %s
                AND hour IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        """, (year, month))
        hourly = [dict(r) for r in cur.fetchall()]
        
        # Daily patterns
        cur.execute("""
            SELECT day_of_week, ROUND(AVG(network_sri_score)::numeric, 1) as sri
            FROM network_reliability_index
            WHERE year = %s AND month = %s
                AND day_of_week IS NOT NULL AND hour IS NULL
            GROUP BY day_of_week
            ORDER BY day_of_week
        """, (year, month))
        daily = [dict(r) for r in cur.fetchall()]
        
        return {"hourly": hourly, "daily": daily}
    finally:
        cur.close()
        conn.close()


def build_prompt(data: dict, request: InsightRequest) -> str:
    """Build the LLM prompt with selected data"""
    
    prompt = """You are a public transport analytics expert. Analyze the following Service Reliability Index (SRI) data for a UK bus network and provide actionable insights.

SRI Score Interpretation:
- 90-100 (Grade A): Excellent service reliability
- 80-89 (Grade B): Good reliability
- 70-79 (Grade C): Acceptable but needs monitoring
- 60-69 (Grade D): Poor reliability, intervention needed
- Below 60 (Grade F): Critical failure, urgent action required

Component Scores (each 0-100):
- Headway Consistency (40% weight): How regular are bus arrivals vs scheduled frequency
- Schedule Adherence (30% weight): Are buses on time vs timetable
- Journey Time Consistency (20% weight): How predictable are journey durations
- Service Delivery (10% weight): Are scheduled services actually running

DATA FOR ANALYSIS:
"""
    
    if request.include_network_summary and data.get("network"):
        n = data["network"]
        prompt += f"""
NETWORK SUMMARY:
- Overall SRI Score: {n.get('network_sri_score', 'N/A')} (Grade {n.get('network_grade', 'N/A')})
- Total Routes Monitored: {n.get('total_routes', 'N/A')}
- Grade Distribution: A:{n.get('routes_grade_a', 0)}, B:{n.get('routes_grade_b', 0)}, C:{n.get('routes_grade_c', 0)}, D:{n.get('routes_grade_d', 0)}, F:{n.get('routes_grade_f', 0)}
- Component Averages: Headway={n.get('avg_headway_score', 'N/A')}, Schedule={n.get('avg_schedule_score', 'N/A')}, Journey Time={n.get('avg_journey_time_score', 'N/A')}, Service={n.get('avg_service_delivery_score', 'N/A')}
"""

    if request.include_operators and data.get("operators"):
        prompt += "\nOPERATOR PERFORMANCE:\n"
        for op in data["operators"]:
            prompt += f"- {op['operator']}: {op['route_count']} routes, Avg SRI {op['avg_sri']}, {op['failing_routes']} failing routes\n"

    if request.include_worst_routes and data.get("routes"):
        worst = [r for r in data["routes"] if r['sri_score'] < 60][:10]
        if worst:
            prompt += "\nWORST PERFORMING ROUTES (Grade F):\n"
            for r in worst:
                prompt += f"- Route {r['route_name']} ({r['direction']}): SRI {r['sri_score']}, H={r['headway_consistency_score']}, S={r['schedule_adherence_score']}, J={r['journey_time_consistency_score']}, D={r['service_delivery_score']}\n"

    if request.include_best_routes and data.get("routes"):
        best = sorted(data["routes"], key=lambda x: x['sri_score'], reverse=True)[:5]
        if best:
            prompt += "\nBEST PERFORMING ROUTES:\n"
            for r in best:
                prompt += f"- Route {r['route_name']} ({r['direction']}): SRI {r['sri_score']} (Grade {r['sri_grade']})\n"

    if request.include_trends and data.get("trends"):
        trends = data["trends"]
        if trends.get("hourly") and len(trends["hourly"]) > 0:
            worst_hour = min(trends["hourly"], key=lambda x: x['sri'])
            best_hour = max(trends["hourly"], key=lambda x: x['sri'])
            prompt += f"\nHOURLY PATTERNS:\n- Worst hour: {worst_hour['hour']:02d}:00 (SRI {worst_hour['sri']})\n- Best hour: {best_hour['hour']:02d}:00 (SRI {best_hour['sri']})\n"
        
        if trends.get("daily") and len(trends["daily"]) > 0:
            days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            worst_day = min(trends["daily"], key=lambda x: x['sri'])
            best_day = max(trends["daily"], key=lambda x: x['sri'])
            prompt += f"DAY OF WEEK PATTERNS:\n- Worst day: {days[worst_day['day_of_week']]} (SRI {worst_day['sri']})\n- Best day: {days[best_day['day_of_week']]} (SRI {best_day['sri']})\n"

    prompt += """

Based on this data, provide your analysis in the following JSON format:
{
    "executive_summary": "2-3 paragraph overview of network health and key concerns",
    "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4"],
    "critical_issues": [
        {"title": "Issue title", "description": "Detailed description", "impact": -5, "routes": ["route1", "route2"]}
    ],
    "opportunities": [
        {"title": "Opportunity title", "description": "Description", "impact": 5}
    ],
    "recommendations": [
        {"priority": "high", "action": "Specific action", "rationale": "Why this matters", "expected_impact": "+5 SRI points", "effort": "low"}
    ]
}

Provide specific, actionable insights based on the actual data. Focus on:
1. Identifying root causes of poor performance
2. Highlighting patterns (time-based, route-based, operator-based)
3. Prioritizing interventions by impact
4. Realistic improvement targets

Return ONLY valid JSON, no markdown or explanations."""

    return prompt


async def call_groq(prompt: str) -> dict:
    """Call Groq API with Llama 3.3"""
    
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a transit analytics expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 4096
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Groq API error: {response.text}")
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Parse JSON from response
        try:
            # Clean up potential markdown code blocks
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")


@router.post("/generate", response_model=InsightResponse)
async def generate_insights(request: InsightRequest):
    """Generate AI-powered insights from SRI data"""
    
    # Find latest available data period
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT year, month FROM service_reliability_index
            WHERE day_of_week IS NULL AND hour IS NULL
            ORDER BY year DESC, month DESC
            LIMIT 1
        """)
        latest = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    
    if latest:
        year = latest['year']
        month = latest['month']
    else:
        raise HTTPException(status_code=404, detail="No SRI data available")
    
    # Gather requested data
    data = {}
    
    if request.include_network_summary:
        data["network"] = get_network_data(year, month)
    
    if request.include_routes or request.include_worst_routes or request.include_best_routes:
        data["routes"] = get_routes_data(year, month)
    
    if request.include_operators:
        data["operators"] = get_operators_data(year, month)
    
    if request.include_trends:
        data["trends"] = get_trends_data(year, month)
    
    # Check if we have any data
    if not data.get("network") and not data.get("routes"):
        raise HTTPException(status_code=404, detail="No SRI data available for current period")
    
    # Build prompt and call LLM
    prompt = build_prompt(data, request)
    llm_response = await call_groq(prompt)
    
    # Return formatted response
    return InsightResponse(
        executive_summary=llm_response.get("executive_summary", ""),
        key_findings=llm_response.get("key_findings", []),
        critical_issues=llm_response.get("critical_issues", []),
        opportunities=llm_response.get("opportunities", []),
        recommendations=llm_response.get("recommendations", []),
        generated_at=datetime.now().isoformat(),
        data_period=f"{year}-{month:02d}"
    )


@router.get("/health")
async def insights_health():
    """Check if insights service is configured"""
    return {
        "groq_configured": bool(GROQ_API_KEY),
        "status": "ready" if GROQ_API_KEY else "missing_api_key"
    }
