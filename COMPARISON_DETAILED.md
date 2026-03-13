# TerriaJS Catalog Generation Comparison: CKAN Plugin vs Airflow DAG

## Executive Summary
Both systems generate similar TerriaJS JSON catalogs with **largely compatible structures**, but there are important differences in architecture, SLD processing sophistication, custom configuration handling, and feature availability. The **plugin is more feature-complete** with dedicated helper classes, while the **DAG is more lightweight** but inline-based.

---

## 1. OUTPUT STRUCTURE COMPARISON

### ✅ BOTH SYSTEMS: Root Structure
Both produce identical root structures:

```json
{
  "catalog": [...],
  "name": "IHP-WINS",
  "baseMaps": {...}  // (optional, plugin-only for modular catalog)
}
```

**Plugin** (line 638-641):
```python
config = {
    "catalog": catalog_members,
    "name": "IHP-WINS"
}
```

**DAG** (line 709):
```python
"name": "IHP-WINS"
```

### ✅ Organization Hierarchy: IDENTICAL
Both use the same 3-level hierarchy: **Org → Dataset → Resource**

**Plugin** (lines 464-469):
```python
dataset_group = {
    "name": dataset_title,
    "type": "group",
    "members": items
}
org_members.append(dataset_group)
```

**DAG** (lines 961-971): Same structure

---

## 2. FORMAT HANDLING COMPARISON

### ✅ IDENTICAL FORMAT SUPPORT
Both support: KML, TIF, TIFF, GeoTIFF (→ COG), CSV, WMS, WMTS, SHP, SHAPE

**Plugin** (line 79):
```python
self.formatos_permitidos = ['KML', 'tif', 'tiff', 'geotiff', 'csv', 'wms', 'wmts', 'shape', 'shp']
```

**DAG** (line 22):
```python
formatos_permitidos = ['KML', 'tif', 'tiff', 'geotiff', 'csv', 'wms', 'wmts', 'shape', 'shp']
```

### ✅ IDENTICAL Format Normalization: TIF → COG
Both normalize tiff formats to "cog"

**Plugin** (lines 114-115):
```python
if resource_format in ["tif", "tiff", "geotiff"]:
    resource_format = "cog"
```

**DAG** (lines 333-334): Identical

---

## 3. RESOURCE ITEM FIELDS COMPARISON

### ✅ BASE FIELDS: IDENTICAL

Both generate identical base resource objects:

```python
elemento = {
    "name": resource_name,
    "type": resource_format,
    "id": resource_id,
    "url": resource_url,
    'description': (notes + '<br/><br/><strong>Dataset URL: </strong> <a href="' + site_url + '/dataset/' + package_id + '">' + site_url + '/dataset/' + package_id + '</a>'),
    "info": [
        {"name": f"Organization: {org_info['display_name']}", "content": f"<img .../><br/>{org_info['description']}<br/>"},
        {"name": "File Description", "content": resource_description},
        {"name": "Availability", "content": resource.get("availability", "")},
        {"name": "Last Modified", "content": resource.get("last_modified", "")},
        {"name": "Created", "content": resource.get("created", "")}
    ],
    "infoSectionOrder": [
        f"Organization: {org_info['display_name']}",
        "About Dataset",
        "File Description",
        "Availability",
        "Last Modified",
        "Created"
    ]
}
```

**Plugin**: lines 121-145
**DAG**: lines 337-361

### ✅ Multi-View Support: IDENTICAL
Both support multiple Terria views per resource

**Plugin** (lines 148-173): Uses `toolkit.get_action('resource_view_list')`
**DAG** (lines 364-398): Uses HTTP POST to `resource_view_list` endpoint

Result: Same name modification: `resource_name = f"{resource_name} - {view_name}"`

### ⚠️ DIFFERENCE: Resource Name Generation
When resource has no name:

**Plugin** (line 108):
```python
resource_name = resource.get('id', f"Resource_{hash(resource.get('url', 'sin_url')) % 10000}")
```

**DAG** (line 328): **IDENTICAL**

---

## 4. SLD PROCESSING COMPARISON

### ⚠️ SIGNIFICANT DIFFERENCE: Architecture

**Plugin**: Uses dedicated `SLDProcessor` class (2596 lines, separate file)
- Methods: `process_cog_sld()`, `process_shp_sld()`
- Enhanced gradient support
- Comprehensive error handling

**DAG**: Inline `process_sld_styles()` function (lines 64-307)
- All logic in one ~300-line function
- No dedicated class structure

### 4.1: COG (Raster) SLD Processing

#### ✅ Core Logic: NEARLY IDENTICAL
Both extract `ColorMapEntry` elements and build color arrays

**Plugin** (lines 546-608 in sld_processor.py):
- Supports `type` attribute on ColorMap: "ramp", "intervals", "values"
- Converts discrete/continuous interpolation types
- Preserves opacity in RGBA format

**DAG** (lines 120-168):
- Simpler parsing: just extracts ColorMapEntry
- No explicit interpolation type handling
- Same RGBA conversion logic

#### ⚠️ DIFFERENCE: Gradient Enhancement
**Plugin ONLY**: Enhanced color gradients for linear interpolation

**Plugin** (line 619):
```python
if len(colors) >= 2 and interpolation_type == "linear":
    colors = self._enhance_color_gradient(colors, interpolation_type)
```

**DAG**: No gradient enhancement

#### ✅ Identical: Transparent Value Filtering

Both filter out transparent colors as "nodata"

**DAG** (lines 414-437):
```python
for quantity_val, rgb_string in colors:
    if rgb_string.startswith("rgba(") and ", 0.0)" in rgb_string:
        nodata_values.append(quantity_val)
    else:
        filtered_colors.append([quantity_val, rgb_string])

render_options = {
    "single": {
        "colors": filtered_colors if filtered_colors else colors,
        "useRealValue": True,
        "type": "discrete"
    }
}
if nodata_values:
    render_options["nodata"] = nodata_values[0] if len(nodata_values) == 1 else nodata_values
```

**Plugin** (sld_processor.py line 651-700): Similar logic in `_apply_raster_renderoptions()`

### 4.2: SHP (Vector) SLD Processing

#### ⚠️ MAJOR DIFFERENCE: Categorical vs Numeric Classification

**DAG** (lines 462-534):
Automatically determines data type and chooses mapping:

```python
numeric_count = 0
categorical_count = 0

for enum_item in style_config['enum_colors']:
    try:
        float(enum_item['value'])
        numeric_count += 1
    except (ValueError, TypeError):
        categorical_count += 1

use_categorical = categorical_count > numeric_count

if use_categorical:
    elemento['styles'] = [{
        "id": "sld-style",
        "color": {
            "mapType": "enum",        # ← Categorical
            "colorColumn": property_name,
            "enumColors": style_config['enum_colors'],
            "nullColor": "#808080"
        }
    }]
else:
    # Configure for numeric data using bin mapping
    elemento['styles'] = [{
        "id": "sld-style",
        "color": {
            "mapType": "bin",         # ← Numeric
            "colorColumn": property_name,
            "binMaximums": bin_maximums,
            "binColors": bin_colors,
            "nullColor": "#808080"
        }
    }]
```

**Plugin** (sld_processor.py): Has similar but in separate methods `process_shp_sld()` with separate enum vs bin generation

#### ⚠️ DIFFERENCE: ElseFilter Handling

**DAG** (lines 200-204):
```python
else_filter = rule.find('.//se:ElseFilter', namespaces)
if else_filter is not None:
    print(f"Rule {i+1}: Found ElseFilter - skipping for categorical styling")
    continue
```

**Plugin** (sld_processor.py): Likely similar but inline in process_shp_sld()

#### ✅ Identical: Shared SHP Properties

Both apply identical properties for shapefiles:

```python
elemento['opacity'] = 0.8
elemento['clampToGround'] = True
elemento['forceCesiumPrimitives'] = False
elemento['legends'] = [{"title": "Legend", "items": style_config['legend_items']}]
```

**DAG**: lines 525-533
**Plugin**: _apply_style_config() method

---

## 5. URL CONSTRUCTION COMPARISON

### ✅ Dataset URL Construction: IDENTICAL

**Plugin** (line 126):
```python
'description': (notes or '') + '<br/><br/><strong>Dataset URL: </strong> <a href="' + 
               site_url + '/dataset/' + package_id + '">' + site_url + '/dataset/' + package_id + '</a>'
```

**DAG** (line 342): **IDENTICAL structure** (but with site_url from config)

### ✅ SLD Style URL Fetching: NEARLY IDENTICAL

Both:
1. Get style_url from Terria view: `selected_view.get('style')`
2. Check for 'NA' string: `if style_url and style_url != 'NA'`
3. Fetch with timeout and retry logic

**Plugin** (lines 245, 55-75): Uses HTTP session with retry strategy
**DAG** (lines 390, 26-33): Identical retry configuration

---

## 6. ORGANIZATION/DATASET METADATA COMPARISON

### ✅ IDENTICAL Org Info Sections

Both retrieve and display:
- Organization display name
- Organization description
- Organization image (image_display_url)

**Plugin** (lines 414-427):
```python
org_data = toolkit.get_action('organization_show')({}, {'id': org_name})
org_info = {
    'display_name': org_data.get('display_name', org_data.get('title', org_name)),
    'description': org_data.get('description', ''),
    'image_display_url': org_data.get('image_display_url', '')
}
```

**DAG** (lines 886-899): Uses HTTP API with same fields

---

## 7. MISSING FEATURES: DAG vs Plugin

### Plugin Has These (DAG Lacks):

1. **Custom Configuration Support with Gist Integration** (Plugin: lines 233-278)
   - Supports Terria sharing URLs with `#share=g-{id}` 
   - Fetches from GitHub gist: `https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/`
   - Applies custom legends, styles, renderOptions, opacity from gist
   
   ```python
   if fragment.startswith('share='):
       gist_id = fragment.split('=g-')[1]
       gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
   ```
   
   **DAG**: Has the same logic! (lines 612-665)

2. **Tag-Based Catalog Generation** (Plugin: lines 494-600)
   - `generate_tag_json(tag_name)` method
   - Creates catalogs filtered by tags
   
   **DAG**: Has `generate_and_upload_catalog_by_tag()` function (lines 990+)

3. **Cache Management** (Plugin: lines 18-19)
   - `CacheManager`: In-memory caching of org/dataset configs
   - `FileCacheManager`: File-based caching for modular catalogs
   - Prevents redundant API calls
   
   **DAG**: No caching, processes from scratch each time

4. **Modular Catalog Generation** (Plugin: lines 694-834)
   - `generate_modular_catalog()` method
   - Creates separate organization reference files with terria-reference type
   - Includes baseMaps configuration
   - Better for large deployments
   
   **DAG**: Only flat/hierarchical structure

5. **SLD Processor Sophistication** (Plugin: 2596 lines)
   - Enhanced color gradients for continuous colormaps
   - Better error handling and multiple encoding attempts
   - Separate methods for COG and SHP processing
   - Handles interpolation type detection
   
   **DAG**: Simpler inline processing

6. **Dedicated HTTP Session with Retry Strategy** (Plugin: lines 55-75)
   - Built-in exponential backoff
   - Handles connection failures gracefully
   - Timeout configuration
   
   **DAG**: Similar but less integrated into class

---

## 8. EXTRA FEATURES: DAG vs Plugin

### DAG Has These (Plugin Lacks):

1. **Airflow Integration** (DAG-specific)
   - Uses Airflow DAG for scheduling
   - Task dependencies and retry policies
   - Cloud-native deployment
   
   **Plugin**: CKAN plugin, runs on-demand via API

2. **Direct File Upload to CKAN** (DAG: lines 771-850)
   - `upload_ckan()` function uploads generated JSONs as CKAN resources
   - Creates resource version history
   - Manages resource metadata
   
   **Plugin**: No direct CKAN resource management (returns JSON to caller)

3. **Automatic Resource Naming** (DAG: lines 793-821)
   - Organization files: `{org_name}.json`
   - Tag files: `tag_{tag_name}.json`
   - Main file: `IHP-WINS.json`
   - Includes descriptions for each type
   
   **Plugin**: No file naming/upload logic

4. **Fallback Styling Logic** (DAG: lines 543-603)
   - Creates basic categorical styling from legend-only data
   - Handles edge cases where style config is incomplete
   
   **Plugin**: Stricter style application

---

## 9. ARCHITECTURAL DIFFERENCES

| Aspect | Plugin | DAG |
|--------|--------|-----|
| **Structure** | Class-based with helper classes | Function-based, monolithic |
| **Caching** | ✅ Memory + file-based | ❌ None |
| **SLD Processing** | ✅ Dedicated SLDProcessor class | ❌ Inline function |
| **Deployment** | CKAN plugin (HTTP API) | Airflow DAG (scheduled) |
| **Scaling** | Per-request generation | Batch generation → upload |
| **Error Handling** | Comprehensive try-catch blocks | Basic error handling |
| **Configuration** | Config classes (ConfigManager) | Hardcoded + Airflow Variables |
| **Dependencies** | CKAN framework | Airflow framework |
| **Modular Output** | ✅ Yes (separate org files) | ❌ Flat hierarchy |
| **Custom Config** | ✅ Gist-based (lines 233-278) | ✅ Gist-based (lines 612-665) |

---

## 10. SPECIFIC CODE EQUIVALENCES

### Custom Config Processing (IDENTICAL LOGIC)

**Plugin** (lines 233-278):
```python
def _apply_custom_config(self, elemento: Dict, custom_config: str):
    parsed_url = urllib.parse.urlparse(custom_config)
    fragment = parsed_url.fragment
    
    if fragment.startswith('share='):
        gist_id = fragment.split('=g-')[1]
        gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
        response = self.http.get(gist_url, timeout=self.TIMEOUT_SECONDS)
        if response.status_code == 200:
            decoded_param = response.text
    else:
        start_param = fragment.split('=', 1)[1]
        decoded_param = urllib.parse.unquote(start_param)
    
    custom_data = json.loads(decoded_param)
    for init_source in custom_data.get('initSources', []):
        # Apply legends, styles, renderOptions, opacity
```

**DAG** (lines 605-680): **IDENTICAL IMPLEMENTATION**

---

## 11. OUTPUT JSON STRUCTURE COMPARISON

### Same Resource Object

```json
{
  "name": "Resource Name - View Name",
  "type": "shp",
  "id": "resource-id-0",
  "url": "https://...",
  "description": "Dataset notes...<br/><br/><strong>Dataset URL: </strong>...",
  "info": [
    {
      "name": "Organization: Org Display Name",
      "content": "<img .../>"
    },
    {"name": "File Description", "content": "..."},
    {"name": "Availability", "content": "..."},
    {"name": "Last Modified", "content": "..."},
    {"name": "Created", "content": "..."}
  ],
  "infoSectionOrder": [
    "Organization: Org Display Name",
    "About Dataset",
    "File Description",
    "Availability",
    "Last Modified",
    "Created"
  ]
}
```

### SHP with Categorical Styling (Both Support)

```json
{
  "name": "Layer Name",
  "type": "shp",
  "styles": [{
    "id": "sld-style",
    "title": "SLD Style (PROPERTY_NAME)",
    "color": {
      "mapType": "enum",
      "colorColumn": "PROPERTY_NAME",
      "enumColors": [
        {"value": "Category1", "color": "#FF0000"},
        {"value": "Category2", "color": "#00FF00"}
      ],
      "nullColor": "#808080"
    }
  }],
  "activeStyle": "sld-style",
  "opacity": 0.8,
  "clampToGround": true,
  "forceCesiumPrimitives": false,
  "legends": [{
    "title": "Legend",
    "items": [
      {"title": "Category1", "color": "#FF0000"},
      {"title": "Category2", "color": "#00FF00"}
    ]
  }]
}
```

### COG with RasterOptions (Both Support)

```json
{
  "name": "Elevation Model",
  "type": "cog",
  "renderOptions": {
    "single": {
      "colors": [[0, "rgb(0,0,0)"], [100, "rgb(255,255,255)"]],
      "useRealValue": true,
      "type": "discrete",
      "domain": [0, 100]
    },
    "nodata": [-9999]
  },
  "opacity": 0.8,
  "legends": [{
    "title": "Legend",
    "items": [
      {"title": "0", "color": "rgb(0,0,0)"},
      {"title": "100", "color": "rgb(255,255,255)"}
    ]
  }]
}
```

---

## 12. CRITICAL COMPATIBILITY NOTES

### ✅ Compatible
- Root structure (`catalog`, `name`)
- Organization hierarchy
- Resource base fields (name, type, id, url, description, info)
- Info sections and ordering
- COG renderOptions structure
- SHP enum/bin styling structure
- Opacity, clampToGround, forceCesiumPrimitives values
- Custom config handling with gist support
- Multi-view support with naming

### ⚠️ Potential Differences
- **Plugin caches results**: DAG recalculates
- **Plugin supports modular output**: DAG produces flat hierarchy
- **DAG uploads to CKAN**: Plugin returns JSON
- **Plugin has SLD gradient enhancement**: DAG doesn't
- **DAG has fallback styling**: Plugin stricter

### ⏱️ Performance Implications
- **Plugin**: Faster subsequent requests (cached), per-request generation
- **DAG**: Slower (recalculates), but batch-optimized with file upload

---

## 13. RECOMMENDATIONS

### For Feature Parity:

1. **If using DAG**: Add caching layer (Redis/memcached) to avoid recalculation
2. **If using Plugin**: Add option to export to CKAN resources like DAG
3. **If migrating**: Verify COG gradient enhancement doesn't break existing visualizations
4. **For SLD**: Both handle enum/bin correctly, but test edge cases with ElseFilter rules

### Testing Priority:

1. ✅ Verify multi-view resources render correctly
2. ✅ Test categorical vs numeric SHP classification
3. ✅ Validate transparent/nodata color handling in COG
4. ✅ Test custom config with gist files
5. ✅ Verify organization metadata (images, descriptions) display

