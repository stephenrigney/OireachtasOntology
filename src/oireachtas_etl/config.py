"""Configuration is deliberately explicit; credentials are environment-only."""
from dataclasses import dataclass
import os
from pathlib import Path

HOUSES_GRAPH = "https://data.oireachtas.ie/graph/houses"
PARTIES_GRAPH = "https://data.oireachtas.ie/graph/parties"
CONSTITUENCIES_GRAPH = "https://data.oireachtas.ie/graph/constituencies"
MEMBERS_API_URL = "https://api.oireachtas.ie/v1/members"
CORE_STATE_DB_FILE = Path.home() / ".local" / "share" / "oireachtas-etl" / "core-state.sqlite"
MEMBERS_LEGACY_STATE_FILE = Path.home() / ".local" / "share" / "oireachtas-etl" / "members-state.json"
BILLS_API_URL = "https://api.oireachtas.ie/v1/legislation"
BILLS_LEGACY_STATE_FILE = Path.home() / ".local" / "share" / "oireachtas-etl" / "bills-state.json"
# Retain these names as aliases for downstream configuration imports.  They
# identify one-time JSON migration inputs, not SQLite databases.
MEMBERS_STATE_FILE = MEMBERS_LEGACY_STATE_FILE
BILLS_STATE_FILE = BILLS_LEGACY_STATE_FILE
REFERENCE_ONTOLOGY_VERSION = "agents.owl.ttl+members.owl.ttl@phase-2-reference-data-2026"

@dataclass(frozen=True)
class Settings:
    api_url: str = "https://api.oireachtas.ie/v1/houses"
    parties_api_url: str = "https://api.oireachtas.ie/v1/parties"
    constituencies_api_url: str = "https://api.oireachtas.ie/v1/constituencies"
    members_api_url: str = MEMBERS_API_URL
    core_state_db_file: Path = CORE_STATE_DB_FILE
    members_legacy_state_file: Path = MEMBERS_LEGACY_STATE_FILE
    bills_api_url: str = BILLS_API_URL
    bills_legacy_state_file: Path = BILLS_LEGACY_STATE_FILE
    raw_dir: Path = Path("data/raw")
    fuseki_gsp_url: str | None = None
    fuseki_sparql_url: str | None = None
    fuseki_user: str | None = None
    fuseki_password: str | None = None
    limit: int = 100
    bills_cursor_overlap_seconds: int = 3600
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
            core_state_db_file=Path(os.getenv("OIR_ETL_STATE_DB", str(cls.core_state_db_file))),
            members_legacy_state_file=Path(os.getenv("OIR_MEMBERS_STATE_FILE", str(cls.members_legacy_state_file))),
            bills_api_url=os.getenv("OIR_BILLS_API_URL", cls.bills_api_url),
            bills_legacy_state_file=Path(os.getenv("OIR_BILLS_STATE_FILE", str(cls.bills_legacy_state_file))),
            raw_dir=Path(os.getenv("OIR_RAW_DIR", "data/raw")),
            fuseki_gsp_url=os.getenv("OIR_FUSEKI_GSP_URL"),
            fuseki_sparql_url=os.getenv("OIR_FUSEKI_SPARQL_URL"),
            fuseki_user=os.getenv("OIR_FUSEKI_USER"),
            fuseki_password=os.getenv("OIR_FUSEKI_PASSWORD"),
            limit=int(os.getenv("OIR_API_LIMIT", "100")),
            bills_cursor_overlap_seconds=int(os.getenv("OIR_BILLS_CURSOR_OVERLAP_SECONDS", "3600")),
            retries=int(os.getenv("OIR_API_RETRIES", "3")),
            timeout=float(os.getenv("OIR_API_TIMEOUT", "30")),
            ontology_version=os.getenv("OIR_ONTOLOGY_VERSION", cls.ontology_version),
            mapping_version=os.getenv("OIR_MAPPING_VERSION", cls.mapping_version),
        )
