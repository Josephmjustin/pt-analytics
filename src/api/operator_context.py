"""
Operator Context Configuration
Hardcoded operator selection for development
Will be replaced with authentication system in production
"""

from enum import Enum
from typing import Optional, List

class OperatorRole(str, Enum):
    """Operator role types"""
    OPERATOR = "operator"
    TRANSPORT_AUTHORITY = "transport_authority"

class Operator:
    """Operator configuration"""
    
    def __init__(
        self, 
        operator_id: str, 
        operator_name: str, 
        role: OperatorRole,
        accessible_operators: Optional[List[str]] = None
    ):
        self.operator_id = operator_id
        self.operator_name = operator_name
        self.role = role
        # For transport authority, accessible_operators is None (means all)
        # For operators, it's a list of their operator names
        self.accessible_operators = accessible_operators or [operator_name] if role == OperatorRole.OPERATOR else None
    
    def can_access_operator(self, operator_name: str) -> bool:
        """Check if this user can access data for given operator"""
        if self.role == OperatorRole.TRANSPORT_AUTHORITY:
            return True  # Transport authority can access all
        return operator_name in (self.accessible_operators or [])
    
    def get_operator_filter(self) -> Optional[List[str]]:
        """
        Get list of operators this user can access
        Returns None if user can access all operators (transport authority)
        """
        if self.role == OperatorRole.TRANSPORT_AUTHORITY:
            return None  # No filter - access all
        return self.accessible_operators

# ==============================================================================
# HARDCODED OPERATOR SELECTION (DEVELOPMENT ONLY)
# ==============================================================================
# Change this to switch between different operator views
# Will be replaced with session/JWT authentication in production

# OPTION 1: Transport Authority (can see all operators)
CURRENT_OPERATOR = Operator(
    operator_id="merseyside_ta",
    operator_name="Merseyside Transport Authority",
    role=OperatorRole.TRANSPORT_AUTHORITY
)

# OPTION 2: Arriva operator
# CURRENT_OPERATOR = Operator(
#     operator_id="arriva",
#     operator_name="Arriva",
#     role=OperatorRole.OPERATOR
# )

# OPTION 3: Stagecoach operator
# CURRENT_OPERATOR = Operator(
#     operator_id="stagecoach",
#     operator_name="Stagecoach",
#     role=OperatorRole.OPERATOR
# )

# OPTION 4: Other operators (uncomment and add as needed)
# CURRENT_OPERATOR = Operator(
#     operator_id="first_bus",
#     operator_name="First Bus",
#     role=OperatorRole.OPERATOR
# )

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_current_operator() -> Operator:
    """Get the currently selected operator (dev) or from session (prod)"""
    # TODO: In production, replace with:
    # return get_operator_from_session() or get_operator_from_jwt()
    return CURRENT_OPERATOR

def get_operator_filter_clause() -> tuple[str, list]:
    """
    Get SQL WHERE clause for operator filtering
    Returns: (where_clause, params)
    """
    operator = get_current_operator()
    operators = operator.get_operator_filter()
    
    if operators is None:
        # Transport authority - no filter
        return "", []
    
    # Single or multiple operators
    placeholders = ", ".join(["%s"] * len(operators))
    return f"operator IN ({placeholders})", operators

def apply_operator_filter(base_query: str, params: list) -> tuple[str, list]:
    """
    Apply operator filter to an existing query
    Args:
        base_query: SQL query that may already have WHERE clause
        params: existing query parameters
    Returns:
        (modified_query, modified_params)
    """
    operator = get_current_operator()
    operators = operator.get_operator_filter()
    
    if operators is None:
        # No filter needed
        return base_query, params
    
    # Check if query already has WHERE
    has_where = "WHERE" in base_query.upper()
    
    placeholders = ", ".join(["%s"] * len(operators))
    if has_where:
        filter_clause = f" AND operator IN ({placeholders})"
    else:
        filter_clause = f" WHERE operator IN ({placeholders})"
    
    # Add filter to query
    modified_query = base_query + filter_clause
    modified_params = params + operators
    
    return modified_query, modified_params

# ==============================================================================
# OPERATOR REGISTRY (for admin/setup purposes)
# ==============================================================================

KNOWN_OPERATORS = {
    "arriva": Operator("arriva", "Arriva", OperatorRole.OPERATOR),
    "stagecoach": Operator("stagecoach", "Stagecoach", OperatorRole.OPERATOR),
    "first_bus": Operator("first_bus", "First Bus", OperatorRole.OPERATOR),
    "merseyside_ta": Operator(
        "merseyside_ta", 
        "Merseyside Transport Authority", 
        OperatorRole.TRANSPORT_AUTHORITY
    ),
}

def get_operator_by_id(operator_id: str) -> Optional[Operator]:
    """Get operator configuration by ID"""
    return KNOWN_OPERATORS.get(operator_id)

# ==============================================================================
# MIGRATION NOTES FOR PRODUCTION AUTHENTICATION
# ==============================================================================
"""
When implementing authentication:

1. Replace CURRENT_OPERATOR with session/JWT token parsing
2. Store operator_id in user session/token claims
3. Update get_current_operator() to read from auth context
4. Add middleware to verify operator access on each request

Example JWT claims:
{
    "user_id": "user123",
    "operator_id": "arriva",
    "role": "operator",
    "email": "manager@arriva.com"
}

Example session structure:
session = {
    "operator": Operator("arriva", "Arriva", OperatorRole.OPERATOR),
    "user_id": "user123",
    "permissions": ["view_routes", "view_reports"]
}

Database schema addition needed:
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    operator_id VARCHAR(50) REFERENCES operators(operator_id),
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE operators (
    operator_id VARCHAR(50) PRIMARY KEY,
    operator_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
"""
