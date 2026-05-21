"""Outside-contact bridge implementations.

Block 3 Piece 3. Each bridge module exports a `cross` function with the
signature:

    def cross(
        bridge_id: str,
        payload: dict[str, Any],
        authorization: dict[str, Any] | None,
        repo: Path,
    ) -> dict[str, Any]:

returning `{resolution, cost_actual, audit}`. Bridge (I, R)s under
`ir/_kernel/bridge/<id>.md` declare `implementation:
<module>:cross` in their frontmatter; `kernel.bridge.cross`
(`src/eightos/sdk/bridge_ops.py`) reads that field at dispatch time
and calls into the bridge module.

Bridges without `implementation:` fall back to the v0.2 echo behavior
of `kernel.bridge.cross`. The `kernel.self` cogito bridge in
particular is unchanged.
"""
