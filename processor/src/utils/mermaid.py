# ───────────────────────── Graph utils ──────────────────────────────
def save_mermaid_png(graph, *, out_file: str = "graph_mermaid.png") -> None:
    """
    Render `graph` as a Mermaid PNG and write it to *out_file*.
    Silently swallows any rendering errors so callers don’t have to.
    """
    try:
        png_bytes = graph.get_graph().draw_mermaid_png()
        with open(out_file, "wb") as fp:
            fp.write(png_bytes)
        print(f"✅ Mermaid diagram saved → {out_file}")
    except Exception as exc:  # pragma: no cover
        print(f"⚠️  Mermaid PNG render failed: {exc}")
