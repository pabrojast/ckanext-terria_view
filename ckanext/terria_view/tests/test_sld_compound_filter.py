"""Regression tests for compound ``ogc:And`` filter handling in SLDProcessor.

Some SLD files (e.g. geological maps published via QGIS/GeoServer) combine
``unit_code = X AND unit_sub = Y`` to discriminate sub-types inside a single
``unit_code``. TerriaJS shp styling can only color by one column, so:

  - the literals of the secondary property (``unit_sub``) must not leak into
    the enum coloring as phantom values that never match a real feature;
  - rules that map the same primary value to different colors must be
    deduplicated deterministically (first occurrence wins, matching the
    rule order in the SLD).

These tests exercise the code path against a minimal SLD that mirrors the
Kenya/Ethiopia compound-filter pattern.
"""

from ckanext.terria_view.sld_processor import SLDProcessor


KENYA_LIKE_SLD = """<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:se="http://www.opengis.net/se"
    version="1.1.0">
  <NamedLayer>
    <se:Name>test</se:Name>
    <UserStyle>
      <se:Name>test</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name>Q2 plain</se:Name>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsEqualTo>
                <ogc:PropertyName>unit_code</ogc:PropertyName>
                <ogc:Literal>Q2</ogc:Literal>
              </ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo>
                <ogc:PropertyName>unit_sub</ogc:PropertyName>
                <ogc:Literal>plain</ogc:Literal>
              </ogc:PropertyIsEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill><se:SvgParameter name="fill">#e6e6e6</se:SvgParameter></se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>Q2 yellow</se:Name>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsEqualTo>
                <ogc:PropertyName>unit_code</ogc:PropertyName>
                <ogc:Literal>Q2</ogc:Literal>
              </ogc:PropertyIsEqualTo>
              <ogc:PropertyIsEqualTo>
                <ogc:PropertyName>unit_sub</ogc:PropertyName>
                <ogc:Literal>yellow</ogc:Literal>
              </ogc:PropertyIsEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill><se:SvgParameter name="fill">#fcef9c</se:SvgParameter></se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>C carbonatites</se:Name>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>unit_code</ogc:PropertyName>
              <ogc:Literal>C</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill><se:SvgParameter name="fill">#00a020</se:SvgParameter></se:Fill>
          </se:PolygonSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
"""


def _enum_values(style_block):
    color_traits = style_block.get('color', {}) or {}
    return [entry['value'] for entry in color_traits.get('enumColors', []) if 'value' in entry]


def test_compound_and_keeps_only_primary_property_values():
    processor = SLDProcessor()
    result = processor.process_shp_sld_from_content(KENYA_LIKE_SLD)

    styles = result.get('styles') or []
    assert styles, f"expected at least one style block, got {result}"
    values = _enum_values(styles[0])

    # Secondary-property literals must not leak in as phantom enum values.
    assert 'plain' not in values, f"unit_sub literal leaked into enumColors: {values}"
    assert 'yellow' not in values, f"unit_sub literal leaked into enumColors: {values}"

    # Primary-property values must be present.
    assert 'Q2' in values, f"primary unit_code value missing from enumColors: {values}"
    assert 'C' in values, f"simple-filter value missing from enumColors: {values}"


def test_compound_and_deduplicates_repeated_primary_values():
    processor = SLDProcessor()
    result = processor.process_shp_sld_from_content(KENYA_LIKE_SLD)

    styles = result.get('styles') or []
    assert styles
    values = _enum_values(styles[0])

    # Two rules map unit_code=Q2 to different colors. The dedupe step keeps
    # only the first occurrence so TerriaJS doesn't see ambiguous mappings.
    assert values.count('Q2') == 1, (
        f"expected exactly one Q2 enumColors entry, got {values.count('Q2')}: {values}"
    )

    # First-wins ordering: Q2 must be colored with the first rule's fill.
    enum_colors = styles[0]['color']['enumColors']
    q2_entry = next(ec for ec in enum_colors if ec['value'] == 'Q2')
    assert q2_entry['color'].lower().startswith('#e6e6e6') or \
        q2_entry['color'].lower().startswith('rgba(230'), \
        f"expected first-rule color for Q2, got {q2_entry['color']}"
