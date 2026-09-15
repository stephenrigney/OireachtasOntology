# Fuseki User Guide

## 1. Start Fuseki

From the repository root:

```bash
docker compose up -d fuseki
```

Check that it is running:

```bash
docker compose ps
```

Open the Fuseki UI:

```text
http://localhost:3030/
```

The configured dataset is:

```text
houses
```

Its main endpoints are:

```text
SPARQL query:
http://localhost:3030/houses/query

Graph Store Protocol:
http://localhost:3030/houses/data
```

## 2. Find the Fuseki admin password

The Docker image uses the `admin` account.

If no password was explicitly configured, inspect the container logs:

```bash
docker compose logs fuseki
```

or:

```bash
docker compose logs fuseki | grep -i password
```

Username:

```text
admin
```

## 3. Configure the ETL client

Set the Fuseki endpoints:

```bash
export OIR_FUSEKI_GSP_URL=http://localhost:3030/houses/data
export OIR_FUSEKI_SPARQL_URL=http://localhost:3030/houses/query
```

Set credentials:

```bash
export OIR_FUSEKI_USER=admin
export OIR_FUSEKI_PASSWORD='<password>'
```

## 4. Load Houses data

Using the repository fixture:

```bash
.venv/bin/oir-etl run houses \
  --fixture data/api_examples/houses.json
```

A successful run should report:

```json
{"published": true, ...}
```

The ETL:

1. transforms the JSON to RDF;
2. validates the RDF;
3. replaces the Houses named graph in Fuseki;
4. runs competency queries against the loaded graph;
5. reports success only when those checks pass.

The graph URI is:

```text
https://data.oireachtas.ie/graph/houses
```

To load current API data instead of the fixture:

```bash
.venv/bin/oir-etl run houses
```

## 5. Check what graphs are loaded

Open:

```text
http://localhost:3030/
```

Select the `houses` dataset and open the query interface.

Run:

```sparql
SELECT ?g (COUNT(*) AS ?triples)
WHERE {
  GRAPH ?g {
    ?s ?p ?o
  }
}
GROUP BY ?g
ORDER BY ?g
```

You should see:

```text
https://data.oireachtas.ie/graph/houses
```

## 6. Inspect raw triples

```sparql
SELECT ?s ?p ?o
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?s ?p ?o
  }
}
LIMIT 50
```

This is useful when checking whether data was loaded at all.

## 7. List House terms

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?term ?label
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?label .
  }
}
ORDER BY ?label
```

Typical results include:

```text
26th Seanad
27th Seanad
33rd Dáil
34th Dáil
Dáil Éireann
Seanad Éireann
```

## 8. Query Dáil terms

```sparql
PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?term ?label ?termNo
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term a oir:DailTerm ;
          skos:prefLabel ?label ;
          oir:termNo ?termNo .
  }
}
ORDER BY DESC(?termNo)
```

## 9. Query Seanad terms

```sparql
PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?term ?label ?termNo
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term a oir:SeanadTerm ;
          skos:prefLabel ?label ;
          oir:termNo ?termNo .
  }
}
ORDER BY DESC(?termNo)
```

## 10. Query term dates

```sparql
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?term ?label ?start ?end
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?label ;
          dct:temporal ?period .

    ?period dcat:startDate ?start .

    OPTIONAL {
      ?period dcat:endDate ?end .
    }
  }
}
ORDER BY DESC(?start)
```

Open-ended current terms will have no `?end` value.

## 11. Find the current House terms

```sparql
PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?term ?label ?start
WHERE {
  GRAPH <https://data.oireachtas.ie/graph/houses> {
    ?term skos:prefLabel ?label ;
          dct:temporal ?period .

    ?period dcat:startDate ?start .

    FILTER NOT EXISTS {
      ?period dcat:endDate ?end .
    }
  }
}
ORDER BY ?label
```

This identifies terms whose source data has no end date.

## 12. Stop Fuseki

Stop the container while retaining its data:

```bash
docker compose stop fuseki
```

Start it again later:

```bash
docker compose start fuseki
```

Or stop the Compose application:

```bash
docker compose down
```

The named Docker volume retains the Fuseki data.

Do **not** use:

```bash
docker compose down -v
```

unless you deliberately want to delete the persistent Fuseki database.

## 13. Reloading data

The ETL uses whole named-graph replacement.

Running:

```bash
.venv/bin/oir-etl run houses
```

again does not append another copy of the Houses records. It replaces:

```text
https://data.oireachtas.ie/graph/houses
```

with the newly validated graph.

This means removed or changed source records do not leave stale triples behind.

## 14. Troubleshooting

### Fuseki UI works but queries return no results

Check whether any named graphs exist:

```sparql
SELECT ?g (COUNT(*) AS ?triples)
WHERE {
  GRAPH ?g {
    ?s ?p ?o
  }
}
GROUP BY ?g
```

If the Houses graph is absent, run the ETL publication command.

### Docker cannot connect to the daemon

If you see an error involving:

```text
dockerDesktopLinuxEngine
```

start Docker Desktop and verify:

```bash
docker info
```

before starting Fuseki.

### Authentication failure

Confirm:

```bash
echo "$OIR_FUSEKI_USER"
```

and ensure `OIR_FUSEKI_PASSWORD` contains the password shown in the Fuseki startup logs.

### Check container logs

```bash
docker compose logs fuseki
```

For live logs:

```bash
docker compose logs -f fuseki
```

## 15. Mental model

There are three separate pieces:

```text
Oireachtas API
      |
      v
   oir-etl
      |
      v
   Fuseki
      |
      v
   SPARQL
```

- **Oireachtas API** is the source.
- **`oir-etl`** extracts, transforms and validates.
- **Fuseki** stores the RDF.
- **SPARQL** is how you query that RDF.

Starting Fuseki does not load data by itself. The ETL publication command populates the named graph.