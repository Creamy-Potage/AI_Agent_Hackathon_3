import os

import sqlalchemy
import vertexai 
from vertexai.generative_models import ( 
    GenerationConfig, 
    GenerativeModel, 
    Tool, 
    grounding, 
)
from zoneinfo import ZoneInfo
from connect_connector import connect_with_connector
from connect_connector_auto_iam_authn import connect_with_connector_auto_iam_authn

def init_connection_pool() -> sqlalchemy.engine.base.Engine:
    # use the connector when INSTANCE_CONNECTION_NAME (e.g. project:region:instance) is defined
    if os.environ.get("INSTANCE_CONNECTION_NAME"):
        return (
            connect_with_connector_auto_iam_authn()
            if os.environ.get("DB_IAM_USER")
            else connect_with_connector()
        )

    raise ValueError(
        "Missing database connection type. Please define one of INSTANCE_CONNECTION_NAME"
    )

db_conn = init_connection_pool()
