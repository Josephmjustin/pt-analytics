"""
Operator name mappings for public-facing display
Maps internal operator names from TransXChange data to consumer-friendly names
"""

OPERATOR_NAME_MAPPINGS = {
    'Ribble Motor Services Ltd': 'Stagecoach',
    # Add more mappings as needed:
    # 'Internal Name': 'Public Name',
}

def normalize_operator_name(operator_name: str) -> str:
    """
    Convert internal operator name to public-facing name
    
    Args:
        operator_name: Internal operator name from TransXChange
        
    Returns:
        Public-facing operator name
    """
    return OPERATOR_NAME_MAPPINGS.get(operator_name, operator_name)

def get_sql_case_statement() -> str:
    """
    Generate SQL CASE statement for operator name mapping
    
    Returns:
        SQL CASE statement string for use in SQL queries
    """
    if not OPERATOR_NAME_MAPPINGS:
        return "operator_name"
    
    cases = "\n                ".join([
        f"WHEN operator_name = '{internal}' THEN '{public}'"
        for internal, public in OPERATOR_NAME_MAPPINGS.items()
    ])
    
    return f"""CASE 
                {cases}
                ELSE operator_name
            END"""