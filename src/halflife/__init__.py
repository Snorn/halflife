"""HalfLife — professional skill maintenance."""

__version__ = "0.1.0"

# Step 1 runs single-tenant against SQLite, but tenant_id is first-class on every
# table from day one so that going multi-tenant (step 3) is a deployment concern,
# not code surgery. See CLAUDE.md.
LOCAL_TENANT_ID = "local"
LOCAL_USER_ID = "local"
