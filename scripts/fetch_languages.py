#!/usr/bin/env python3
"""Suma los bytes de cada lenguaje en tus repos y los guarda en assets/languages.json.

Se ejecuta desde el GitHub Action .github/workflows/languages.yml. Cuenta solo
los repos propios que no son fork. Con el GITHUB_TOKEN del Action solo ve los
repos públicos; para incluir los privados, crea un secreto LANGS_TOKEN con un
token personal (permiso de lectura de repos).

Uso local:
    GH_TOKEN=... python3 scripts/fetch_languages.py
"""

import json
import os
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER", "jfpanchi")
# Lenguajes que no se cuentan (los mismos que ocultabas en la tarjeta anterior).
HIDE = {"Jupyter Notebook", "HTML"}
OUT = Path(__file__).resolve().parent.parent / "assets" / "languages.json"

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def graphql(token, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if body.get("errors"):
        raise SystemExit(f"GitHub API error: {body['errors']}")
    return body["data"]["user"]["repositories"]


def main():
    token = os.environ["GH_TOKEN"]
    totals, repos, cursor = {}, 0, None
    while True:
        page = graphql(token, {"login": USER, "cursor": cursor})
        for repo in page["nodes"]:
            repos += 1
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                if name not in HIDE:
                    totals[name] = totals.get(name, 0) + edge["size"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    languages = sorted(({"name": n, "bytes": b} for n, b in totals.items()), key=lambda l: -l["bytes"])
    OUT.write_text(json.dumps({"repos": repos, "languages": languages}, indent=2) + "\n", encoding="utf-8")
    print(f"{repos} repos, {len(languages)} languages -> {OUT.name}")


if __name__ == "__main__":
    main()
