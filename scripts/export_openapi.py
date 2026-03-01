import json
import os
import sys

# Add the parent directory to sys.path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


def export_openapi():
    openapi_schema = app.openapi()
    
    # Path to save the schema
    # We want to save it to web/public so it can be served
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web", "public", "openapi.json")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print(f"OpenAPI schema exported to {output_path}")

if __name__ == "__main__":
    export_openapi()
