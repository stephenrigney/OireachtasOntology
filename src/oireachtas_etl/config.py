"""Configuration is deliberately explicit; credentials are environment-only."""
from dataclasses import dataclass
import os
from pathlib import Path

HOUSES_GRAPH = "https://data.oireachtas.ie/graph/houses"
PARTIES_GRAPH = "https://data.oireachtas.ie/graph/parties"
CONSTITUENCIES_GRAPH = "https://data.oireachtas.ie/graph/constituencies"
MEMBERS_API_URL = "https://api.oireachtas.ie/v1/members"
MEMBERS_STATE_FILE = Path.home() / ".local" / "share" / "oireachtas-etl" / "members-state.json"
REFERENCE_ONTOLOGY_VERSION = "agents.owl.ttl+members.owl.ttl@phase-2-reference-data-2026"

@dataclass(frozen=True)
class Settings:
    api_url: str = "https://api.oireachtas.ie/v1/houses"
    parties_api_url: str = "https://api.oireachtas.ie/v1/parties"
    constituencies_api_url: str = "https://api.oireachtas.ie/v1/constituencies"
    members_api_url: str = MEMBERS_API_URL
    members_state_file: Path = MEMBERS_STATE_FILE
    raw_dir: Path = Path("data/raw")
    fuseki_gsp_url: str | None = None
    fuseki_sparql_url: str | None = None
    fuseki_user: str | None = None
    fuseki_password: str | None = None
    limit: int = 100
    retries: int = 3
    timeout: float = 30.0
    ontology_version: str = "agents.owl.ttl@phase-1-houses-2026"
    mapping_version: str = "houses_mapping.csv@phase-1-houses-2026"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            api_url=os.getenv("OIR_API_URL", cls.api_url),
            parties_api_url=os.getenv("OIR_PARTIES_API_URL", cls.parties_api_url),
            constituencies_api_url=os.getenv("OIR_CONSTITUENCIES_API_URL", cls.constituencies_api_url),
            members_api_url=os.getenv("OIR_MEMBERS_API_URL", cls.members_api_url),
            members_state_file=Path(os.getenv("OIR_MEMBERS_STATE_FILE", str(cls.members_state_file))),
            raw_dir=Path(os.getenv("OIR_RAW_DIR", "data/raw")),
            fuseki_gsp_url=os.getenv("OIR_FUSEKI_GSP_URL"),
            fuseki_sparql_url=os.getenv("OIR_FUSEKI_SPARQL_URL"),
            fuseki_user=os.getenv("OIR_FUSEKI_USER"),
            fuseki_password=os.getenv("OIR_FUSEKI_PASSWORD"),
            limit=int(os.getenv("OIR_API_LIMIT", "100")),
            retries=int(os.getenv("OIR_API_RETRIES", "3")),
            timeout=float(os.getenv("OIR_API_TIMEOUT", "30")),
            ontology_version=os.getenv("OIR_ONTOLOGY_VERSION", cls.ontology_version),
            mapping_version=os.getenv("OIR_MAPPING_VERSION", cls.mapping_version),
        )
