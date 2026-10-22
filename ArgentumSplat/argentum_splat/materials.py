"""Redshift node materials for Argentum Splat, Cinema 4D 2027.

Run these functions on Cinema 4D's main thread. The mesh contract is:

* four unshared points per splat;
* UVW coordinates spanning (0, 0) to (1, 1) on every quad;
* ``SplatColor`` Vertex Color tag containing linear RGB;
* ``SplatOpacity`` Vertex Map tag containing alpha in [0, 1];
* ``SplatEmission``, ``SplatDiffuse`` and ``SplatSubsurface`` Vertex Maps
  containing the corresponding surface weights.

Quad half-extents are three Gaussian standard deviations. The OSL expression
therefore evaluates exp(-0.5 * ((3*x)**2 + (3*y)**2)). Like the original 3DGS
rasterizer, contributions below 1/255 are discarded and alpha is capped at .99.
Discarding nearly transparent corners also avoids unnecessary transparency
intersections in a ray tracer. The shader is embedded in the material.

The Redshift Standard Material is deliberately selected: its thin-walled
subsurface weight is diffuse transmission, suitable for zero-thickness cards.
The function never changes document renderer, color management or ray depth.
"""

import math

import c4d
import maxon
from . import ids as I


NODE_SPACE = maxon.Id("com.redshift3d.redshift4c4d.class.nodespace")
CORE = "com.redshift3d.redshift4c4d.nodes.core."
OSL = "com.redshift3d.redshift4c4d.node.osl."
OUTPUT = "com.redshift3d.redshift4c4d.node.output."
COLOR_TAG = "SplatColor"
OPACITY_TAG = "SplatOpacity"
WEIGHT_MAPS = (
    ("emission_weight", "as_emission", "SplatEmission", "emission_weight"),
    ("diffuse_weight", "as_diffuse", "SplatDiffuse", "base_color_weight"),
    ("subsurface_weight", "as_subsurface", "SplatSubsurface", "ms_amount"),
)

LEGACY_GAUSSIAN_SOURCE = """shader ArgentumGaussian(
    float SplatOpacity = 1.0,
    output color GaussianOpacity = color(1.0)
)
{
    float x = 2.0 * u - 1.0;
    float y = 2.0 * v - 1.0;
    float alpha = clamp(SplatOpacity, 0.0, 1.0);
    GaussianOpacity = color(alpha * exp(-4.5 * (x*x + y*y)));
}
"""

GAUSSIAN_SOURCE = """shader ArgentumGaussian(
    float SplatOpacity = 1.0,
    output color GaussianOpacity = color(1.0)
)
{
    float x = 2.0 * u - 1.0;
    float y = 2.0 * v - 1.0;
    float alpha = min(0.99, clamp(SplatOpacity, 0.0, 1.0)
                            * exp(-4.5 * (x*x + y*y)));
    GaussianOpacity = color(alpha < (1.0 / 255.0) ? 0.0 : alpha);
}
"""

LEGACY_EMISSION_SOURCE = """shader ArgentumEmissionColor(
    color SplatColor = color(1.0),
    float EmissionWeight = 1.0,
    output color WeightedColor = color(1.0)
)
{
    WeightedColor = SplatColor * max(0.0, EmissionWeight);
}
"""

# Keep distinct generated kernel names when migrating shader implementations.
# Reusing an entry name for a different OSL program can invalidate Redshift's
# compiled shader cache even when the graph reports a successful compilation.
EMISSION_SOURCE = LEGACY_EMISSION_SOURCE.replace(
    'shader ArgentumEmissionColor(', 'shader ArgentumEmissionColor060(')

DEFAULTS = {
    "emission_weight": I.DEFAULTS[I.EMISSION],
    "diffuse_weight": I.DEFAULTS[I.DIFFUSE],
    "subsurface_weight": I.DEFAULTS[I.SUBSURFACE],
}


class MaterialError(RuntimeError):
    """A required Redshift graph node or port is unavailable."""


def _main_thread():
    if not c4d.threading.GeIsMainThread():
        raise MaterialError("Redshift material changes must run on the main thread.")


def _root(graph):
    return graph.GetViewRoot()


def _input(node, name):
    port = node.GetInputs().FindChild(name)
    if port.IsNullValue():
        raise MaterialError("Required Redshift input is unavailable: " + name)
    return port


def _output(node, name):
    port = node.GetOutputs().FindChild(name)
    if port.IsNullValue():
        raise MaterialError("Required Redshift output is unavailable: " + name)
    return port


def _node(graph, node_id):
    node = _root(graph).FindChild(node_id)
    if node.IsNullValue():
        raise MaterialError("Argentum material node is missing: " + node_id)
    return node


def _setting(settings, name):
    """Reject bad values rather than committing a partially broken graph."""
    value = float(settings.get(name, DEFAULTS[name]))
    if not math.isfinite(value):
        raise MaterialError(name + " must be finite.")
    maximum = 100.0 if name == "emission_weight" else 1.0
    return max(0.0, min(maximum, value))


def _weights(settings):
    return {name: _setting(settings, name) for name in DEFAULTS}


def _begin_transaction(graph, undo_mode=None):
    """Optionally join a caller-owned native document undo action.

    A default Nodes transaction opens its own undo action, even inside
    BaseDocument.StartUndo(). ADD keeps OSL migrations and weight updates in
    the same user undo step as the splat object's parameter changes.
    """
    if undo_mode is None:
        return graph.BeginTransaction()
    user_data = maxon.DataDictionary()
    user_data.Set(maxon.nodes.UndoMode, undo_mode)
    return graph.BeginTransaction(user_data)


def _set_weights(surface, values):
    prefix = CORE + "standardmaterial."
    # Redshift 2027 accepts a wire on emission_weight but renders it as zero.
    # Multiply the emission color instead; radiance is mathematically identical.
    _input(surface, prefix + "emission_weight").SetPortValue(1.0)
    _input(surface, prefix + "base_color_weight").SetPortValue(values["diffuse_weight"])
    _input(surface, prefix + "ms_amount").SetPortValue(values["subsurface_weight"])


def _weight_maps(graph, surface, values):
    """Read weights from geometry, with material defaults for missing maps.

    Keeping the data on each generated mesh allows independently animated
    objects and their render clones to safely share one node material.
    This also upgrades materials created by the earlier five-node graph.
    Must be called inside a graph transaction.
    """
    attribute = CORE + "vertexattributelookup."
    prefix = CORE + "standardmaterial."
    _set_weights(surface, values)
    emission = _node(graph, "as_emission_color")
    _input(surface, prefix + "emission_weight").RemoveConnections(
        maxon.PORT_DIR.INPUT, maxon.Wires.All()
    )
    for setting, node_id, tag_name, target in WEIGHT_MAPS:
        node = _root(graph).FindChild(node_id)
        if node.IsNullValue():
            node = graph.AddChild(
                maxon.Id(node_id), maxon.Id(CORE + "vertexattributelookup")
            )
            node.SetValue(maxon.NODE.BASE.NAME, tag_name + " — surface weight")
            _input(node, attribute + "attribute").SetPortValue(tag_name)
        destination = (_input(emission, OSL + "emissionweight")
                       if setting == "emission_weight"
                       else _input(surface, prefix + target))
        destination.RemoveConnections(maxon.PORT_DIR.INPUT, maxon.Wires.All())
        _output(node, attribute + "outscalar").Connect(destination)
        _input(node, attribute + "defaultscalar").SetPortValue(values[setting])
    emission_color = _input(surface, prefix + "emission_color")
    emission_color.RemoveConnections(maxon.PORT_DIR.INPUT, maxon.Wires.All())
    _output(_node(graph, "as_color"), attribute + "outcolor").Connect(
        _input(emission, OSL + "splatcolor")
    )
    _output(emission, OSL + "weightedcolor").Connect(emission_color)


def _ensure_emission_node(graph, undo_mode=None):
    """Compile the color multiplier before connecting its dynamic ports."""
    existing = _root(graph).FindChild("as_emission_color")
    if not existing.IsNullValue():
        source = _input(existing, OSL + "internal.sourcecode")
        if str(source.GetPortValue()).strip() == LEGACY_EMISSION_SOURCE.strip():
            with _begin_transaction(graph, undo_mode) as transaction:
                source.SetPortValue(EMISSION_SOURCE)
                transaction.Commit()
        return
    with _begin_transaction(graph, undo_mode) as transaction:
        node = graph.AddChild(maxon.Id("as_emission_color"), maxon.Id(OSL.rstrip(".")))
        node.SetValue(maxon.NODE.BASE.NAME, "Emission color × SplatEmission")
        _input(node, OSL + "internal.sourcemode").SetPortValue(0)
        _input(node, OSL + "internal.sourcecode").SetPortValue(EMISSION_SOURCE)
        transaction.Commit()
    _output(_node(graph, "as_emission_color"), OSL + "weightedcolor")


def _upgrade_gaussian_node(graph, undo_mode=None):
    """Upgrade only our unmodified old shader; preserve hand-edited shaders.

    The input/output names remain identical, so the existing opacity map and
    surface connections can be retained. Compile in its own transaction before
    reading the dynamic ports, as with a newly created OSL node.
    """
    node = _node(graph, "as_gaussian")
    source = _input(node, OSL + "internal.sourcecode")
    if str(source.GetPortValue()).strip() != LEGACY_GAUSSIAN_SOURCE.strip():
        return False
    with _begin_transaction(graph, undo_mode) as transaction:
        source.SetPortValue(GAUSSIAN_SOURCE)
        transaction.Commit()
    node = _node(graph, "as_gaussian")
    _input(node, OSL + "splatopacity")
    _output(node, OSL + "gaussianopacity")
    return True


def create_material(doc, name="Argentum Splat", settings=None):
    """Create, insert and return an editable Redshift material.

    Only the material is added to ``doc``. Callers own the undo transaction.
    On failure the new material is removed and MaterialError is raised; a
    legacy material is never silently substituted.
    """
    _main_thread()
    if doc is None:
        raise MaterialError("A Cinema 4D document is required.")
    values = _weights(settings or {})
    material = c4d.BaseMaterial(c4d.Mmaterial)
    if material is None:
        raise MaterialError("Cinema 4D could not allocate a material.")
    material.SetName(name)
    doc.InsertMaterial(material)
    try:
        node_material = material.GetNodeMaterialReference()
        node_material.CreateEmptyGraph(NODE_SPACE)
        graph = node_material.GetGraph(NODE_SPACE)
        if graph.IsNullValue():
            raise MaterialError("Redshift node space is unavailable.")

        with graph.BeginTransaction() as transaction:
            surface = graph.AddChild(
                maxon.Id("as_surface"), maxon.Id(CORE + "standardmaterial")
            )
            output = graph.AddChild(
                maxon.Id("as_output"), maxon.Id(OUTPUT.rstrip("."))
            )
            color = graph.AddChild(
                maxon.Id("as_color"), maxon.Id(CORE + "vertexattributelookup")
            )
            opacity = graph.AddChild(
                maxon.Id("as_opacity"), maxon.Id(CORE + "vertexattributelookup")
            )
            gaussian = graph.AddChild(
                maxon.Id("as_gaussian"), maxon.Id(OSL.rstrip("."))
            )
            for node, label in (
                (surface, "Splat Surface"),
                (output, "Redshift Output"),
                (color, "SplatColor — linear RGB"),
                (opacity, "SplatOpacity — alpha"),
                (gaussian, "Gaussian falloff — 3 sigma"),
            ):
                node.SetValue(maxon.NODE.BASE.NAME, label)
            attribute = CORE + "vertexattributelookup."
            _input(color, attribute + "attribute").SetPortValue(COLOR_TAG)
            _input(color, attribute + "defaultcolor").SetPortValue(
                maxon.ColorA(1.0, 0.0, 1.0, 1.0)
            )
            _input(opacity, attribute + "attribute").SetPortValue(OPACITY_TAG)
            # Missing alpha data must be conspicuous rather than silently opaque.
            _input(opacity, attribute + "defaultscalar").SetPortValue(0.0)
            _input(gaussian, OSL + "internal.sourcemode").SetPortValue(0)
            _input(gaussian, OSL + "internal.sourcecode").SetPortValue(GAUSSIAN_SOURCE)
            transaction.Commit()

        # OSL compiles on transaction commit and publishes its dynamic ports.
        gaussian = _node(graph, "as_gaussian")
        compilation = str(_input(gaussian, OSL + "internal.messages").GetPortValue())
        if _output(gaussian, OSL + "gaussianopacity").IsNullValue():
            raise MaterialError("Gaussian OSL could not compile: " + compilation)
        _ensure_emission_node(graph)

        with graph.BeginTransaction() as transaction:
            surface = _node(graph, "as_surface")
            output = _node(graph, "as_output")
            color = _node(graph, "as_color")
            opacity = _node(graph, "as_opacity")
            prefix = CORE + "standardmaterial."
            _weight_maps(graph, surface, values)
            for name, value in (
                ("refl_weight", 0.0),
                ("coat_weight", 0.0),
                ("sheen_weight", 0.0),
                ("refr_weight", 0.0),
                ("metalness", 0.0),
                ("diffuse_roughness", 0.0),
            ):
                _input(surface, prefix + name).SetPortValue(value)
            _input(surface, prefix + "refr_thin_walled").SetPortValue(True)
            _input(surface, prefix + "overallaffectsemission").SetPortValue(False)
            for target in ("base_color", "ms_color"):
                _output(color, attribute + "outcolor").Connect(
                    _input(surface, prefix + target)
                )
            _output(opacity, attribute + "outscalar").Connect(
                _input(gaussian, OSL + "splatopacity")
            )
            _output(gaussian, OSL + "gaussianopacity").Connect(
                _input(surface, prefix + "opacity_color")
            )
            _output(surface, prefix + "outcolor").Connect(
                _input(output, OUTPUT + "surface")
            )
            transaction.Commit()
        material.Message(c4d.MSG_UPDATE)
        return material
    except Exception as error:
        material.Remove()
        if isinstance(error, MaterialError):
            raise
        raise MaterialError("Cannot create the Redshift splat material: " + str(error)) from error


def update_material(material, settings, *, undo_mode=None):
    """Update fallback weights, adding map nodes to older materials if needed.

    Missing settings use the documented defaults. Call on the main thread;
    callers own undo recording. Pass maxon.nodes.UNDO_MODE.ADD inside an open
    document undo action to include every graph transaction in that action.
    Omitting undo_mode preserves the standard Nodes API undo behavior.
    Color correction and spherical harmonics are
    evaluated by the splat generator and supplied through ``SplatColor``.
    Existing geometry weight maps take precedence over these defaults.
    """
    _main_thread()
    if material is None:
        raise MaterialError("An Argentum Splat material is required.")
    values = _weights(settings or {})
    graph = material.GetNodeMaterialReference().GetGraph(NODE_SPACE)
    if graph.IsNullValue():
        raise MaterialError("The material has no Redshift graph.")
    surface = _node(graph, "as_surface")
    _upgrade_gaussian_node(graph, undo_mode)
    _ensure_emission_node(graph, undo_mode)
    with _begin_transaction(graph, undo_mode) as transaction:
        _weight_maps(graph, surface, values)
        transaction.Commit()
    material.Message(c4d.MSG_UPDATE)
    return material


def inspect_material(material):
    """Return a compact graph audit useful for support and integration tests."""
    graph = material.GetNodeMaterialReference().GetGraph(NODE_SPACE)
    surface = _node(graph, "as_surface")
    gaussian = _node(graph, "as_gaussian")
    prefix = CORE + "standardmaterial."
    return {
        "node_space": str(NODE_SPACE),
        "node_count": sum(
            node.GetKind() == maxon.NODE_KIND.NODE
            for node in _root(graph).GetChildren()
        ),
        "emission_weight": float(_input(
            _node(graph, "as_emission"),
            CORE + "vertexattributelookup.defaultscalar"
        ).GetPortValue()),
        "diffuse_weight": float(_input(surface, prefix + "base_color_weight").GetPortValue()),
        "subsurface_weight": float(_input(surface, prefix + "ms_amount").GetPortValue()),
        "thin_walled": bool(_input(surface, prefix + "refr_thin_walled").GetPortValue()),
        "reflection_weight": float(_input(surface, prefix + "refl_weight").GetPortValue()),
        "osl_messages": str(_input(gaussian, OSL + "internal.messages").GetPortValue()),
        "gaussian_opacity_profile": (
            "3DGS: alpha cap 0.99, contribution cutoff 1/255"
            if str(_input(gaussian, OSL + "internal.sourcecode").GetPortValue()).strip()
            == GAUSSIAN_SOURCE.strip() else "custom or legacy"
        ),
        "color_tag": COLOR_TAG,
        "opacity_tag": OPACITY_TAG,
        "weight_tags": {setting: tag for setting, _, tag, _ in WEIGHT_MAPS},
        "weight_map_fallbacks": {
            setting: float(_input(
                _node(graph, node_id),
                CORE + "vertexattributelookup.defaultscalar"
            ).GetPortValue())
            for setting, node_id, _, _ in WEIGHT_MAPS
        },
    }
