# HTFS: Hierarchically Tagged File System
## Technical Design Document

**Version**: 1.0  
**Date**: March 2026  
**System**: HTFS-SPARQL - A Hierarchical Tag-driven File Organization System

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Data Model & Ontology](#data-model--ontology)
5. [API & Interfaces](#api--interfaces)
6. [Query Processing Pipeline](#query-processing-pipeline)
7. [Storage & Persistence](#storage--persistence)
8. [Design Patterns](#design-patterns)
9. [Use Cases & Workflows](#use-cases--workflows)
10. [Performance Considerations](#performance-considerations)
11. [Future Extensions](#future-extensions)

---

## Executive Summary

HTFS is an innovative file organization system that decouples tagging from traditional filesystem hierarchies. The system enables:

- **Hierarchical Tags**: Tags organized in multiple parent-child relationships forming a directed acyclic graph (DAG)
- **Multi-tag Assignment**: Files and directories can have multiple tags across the hierarchy
- **Transitive Queries**: Searching by parent tags automatically includes all children in results
- **SPARQL-based Querying**: Complex tag expressions evaluated through RDF/SPARQL
- **RDF Persistence**: All metadata stored in a single auxiliary `.tagfs.ttl` file in Turtle format
- **CLI-driven Workflow**: Command-line interface for scripting and automation
- **Filesystem Integration**: Optional inotify daemon for automatic resource tracking on changes

### Key Innovation
Unlike traditional folders (which form a strict tree hierarchy), HTFS tags form a **hierarchical graph** where each tag can have multiple parents. When searching for a parent tag, the system automatically includes all descendant tags in the results, enabling intuitive, real-world classification schemes.

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                   CLI Layer (tagfs.py)              │
│  Commands: init, lstags, addtags, linktags, etc.   │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│           Utilities Layer (TagfsUtilities.py)       │
│  • Hierarchical tag handling                        │
│  • Resource normalization & management              │
│  • Tag expression evaluation                        │
│  • Filesystem boundary detection                    │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼─────────┐  ┌────────▼────────────────┐
│  TagService.py  │  │ QueryEvaluator.py       │
│  • High-level   │  │ • AST Parser            │
│    Tag/Resource │  │ • Query Compilation     │
│    operations   │  │ • SPARQL Generation     │
└───────┬─────────┘  └────────┬────────────────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────────────────┐
        │   RDFHandler.py (Core Layer)    │
        │  • GraphManager                 │
        │  • TagRepository                │
        │  • ResourceRepository           │
        │  • SPARQL Execution             │
        └──────────┬───────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │   RDFLib Graph (in-memory)      │
        │   ↓ Serialized to .tagfs.ttl    │
        │   (Turtle Format on Disk)       │
        └─────────────────────────────────┘
```

### Component Interaction Flow

```
User
  ↓
CLI Parser (tagfs.py)
  ↓
Handler Functions (_add_tags, _tag_resource, etc.)
  ↓
TagfsUtilities.TagfsTagHandlerUtilities
  ├→ Normalize URL paths
  ├→ Parse hierarchical tags
  └→ Delegate to TagService
      ↓
    TagService
      ├→ TagRepository (CRUD for tags)
      │  └→ SPARQL queries on graph
      ├→ ResourceRepository (CRUD for resources)
      │  └→ SPARQL queries on graph
      └→ QueryEvaluator (for complex expressions)
          └→ AST → SPARQL compilation
          ↓
      GraphManager
      ├→ Load .tagfs.ttl into rdflib Graph
      ├→ Execute SPARQL queries
      ├→ Manage RDF triples
      └→ Serialize & save changes
```

---

## Core Components

### 1. **CLI Layer (tagfs.py)**

The command-line interface providing user-facing operations.

#### Key Responsibilities:
- Parse command-line arguments
- Dispatch to appropriate handler functions
- Provide help and usage information
- Handle file system changes (optional)

#### Command Categories:

**Initialization**:
- `init`: Initialize tagfs database in current directory

**Tag Management**:
- `lstags [tag]*`: List all tags or filter by patterns
- `addtags tag1 tag2 ...`: Add new tags
- `renametag tag newtag`: Rename existing tag
- `linktags tag parenttag`: Create parent-child relationship
- `unlinktags tag parenttag`: Remove relationship (unimplemented)

**Resource Management**:
- `addresource path`: Track a new file/directory
- `rmresource path`: Untrack a resource
- `mvresource path newpath`: Move tracked resource
- `tagresource path tag1 tag2 ...`: Assign tags to resource
- `untagresource path tag1 tag2 ...`: Remove tags from resource
- `getresourcetags path`: List tags on a resource
- `rmresourcetags path`: Remove all tags from a resource

**Querying**:
- `lsresources tagexpr`: Query resources using tag expressions (e.g., `(proj1|proj2)&research&~draft`)

**System**:
- `getboundary`: Return filesystem boundary (root where .tagfs.ttl exists)
- `help`: Display usage information

#### Implementation Pattern:
```python
def _handler_function(args):
    th_utils = get_tagfs_utils()  # Get TagfsUtilities instance
    # Perform operation
    # Return exit code (0 = success, 1 = error)
```

---

### 2. **Utilities Layer (TagfsUtilities.py)**

Provides high-level abstractions and convenience functions.

#### Key Class: `TagfsTagHandlerUtilities`

**Responsibilities**:
- Filesystem boundary detection
- URL path normalization (relative to tagfs boundary)
- Hierarchical tag parsing and processing
- Convenience wrappers around TagService
- Resource tracking validation

#### Key Methods:

| Method | Purpose |
|--------|---------|
| `get_tags_list(tags)` | List tags, optionally filtering by closure |
| `add_tags(tags)` | Add tags with optional hierarchy (separated by `/`) |
| `rename_tag(tag, new_tag)` | Rename tag while maintaining relationships |
| `add_resource(path)` | Track new resource |
| `tag_resource(path, tags)` | Assign tags to resource |
| `get_resources_by_tag_expr(expr)` | Query resources using tag expressions |
| `link_tags(tag, parent)` | Create hierarchical link |
| `is_resource_tracked(path)` | Check if resource is in database |

#### Hierarchical Tag Syntax:
```
addtags "Project/Alpha/Reports"
```
Creates tags: `Project`, `Alpha`, `Reports` with relationships:
- `Alpha` has parent `Project`
- `Reports` has parent `Alpha`

#### URL Normalization:
- Converts absolute filesystem paths to relative paths from tagfs boundary
- Enables portability: .tagfs.ttl can move with its directory
- Normalizes path separators to `/` for consistency across platforms

---

### 3. **High-Level Service Layer (TagService.py)**

Provides a unified interface for tag and resource operations.

#### Key Class: `TagService`

**Initialization**:
```python
ts = TagService(db_path)  # .tagfs.ttl path
ts.initialize()  # Create schema if needed
```

**Wraps Two Repository Objects**:
1. `TagRepository`: Low-level tag operations
2. `ResourceRepository`: Low-level resource operations

#### Tag Operations:
- `add_tag(tag_name)`: Create new tag
- `rename_tag(tag_name, new_name)`: Rename tag
- `link_tag(tag_name, parent_name)`: Create hierarchy link
- `unlink_tag(tag_name, parent_name)`: Remove hierarchy link
- `get_tag_id(tag_name)`: Retrieve numeric ID
- `get_tag_name(tag_id)`: Retrieve name by ID
- `get_tag_list()`: List all tags
- `get_tag_closure(tags)`: Get tags plus all descendants

#### Resource Operations:
- `add_resource(url)`: Track new resource
- `add_resource_tags(url, tags)`: Assign tags
- `del_resource_tags(url, tags)`: Remove tags
- `get_resource_tags(url)`: Retrieve tags on resource
- `get_resources_by_tag(tags)`: Find resources with given tags
- `update_resource_url(old_url, new_url)`: Move resource
- `del_resource(url)`: Untrack resource

#### Design Pattern:
Acts as a **Facade** over the repository layer, providing a simpler interface for common operations.

---

### 4. **RDF Layer (RDFHandler.py)**

Core persistence and semantic query engine.

#### Key Classes:

##### **GraphManager**
Manages RDF graph lifecycle and serialization.

**Design**:
- Wraps `rdflib.Graph` for RDF operations
- Handles `.tagfs.ttl` file I/O
- One graph per database instance

**Key Methods**:
- `connect()`: Load graph from disk or create new
- `close()`: Persist graph to disk
- `initialize_schema()`: Set up metadata counters
- Context manager support: `with GraphManager() as gm:`

**Storage Format**: Turtle (`.ttl`)
```turtle
@prefix htfs: <http://htfs.example.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

htfs:tag_Project a skos:Concept ;
    skos:prefLabel "Project" ;
    htfs:id 1 .
```

**Metadata Reserved**:
- `htfs:meta` - Reserved URI for schema metadata
- `htfs:maxTagId` - Highest tag ID issued
- `htfs:maxResourceId` - Highest resource ID issued

##### **TagRepository**
SPARQL-based tag CRUD operations.

**Core Entities**:
- **Tag URI**: `htfs:tag_{tag_name}` (unique identifier)
- **Type**: `skos:Concept` (SKOS vocabulary)
- **Properties**:
  - `skos:prefLabel`: Display name
  - `htfs:id`: Numeric ID (for efficiency)
  - `skos:broader`: Parent tag relationship

**Key Methods**:

| Method | Implementation |
|--------|-----------------|
| `add_tag(name)` | Allocate ID, create RDF triples with type + label |
| `get_tag_id(name)` | SPARQL query: find `htfs:id` by `skos:prefLabel` |
| `get_tag_name(id)` | SPARQL query: find `skos:prefLabel` by `htfs:id` |
| `link_tag(child, parent)` | Add triple: `child skos:broader parent` |
| `get_downstream_tags(tag)` | SPARQL transitive closure: `skos:broader+` |
| `get_tag_closure(tags)` | Expand tags with all descendants |

**Tag Hierarchy SPARQL Example**:
```sparql
# Get all descendants of "Project" tag
SELECT ?label WHERE {
    ?descendant skos:broader+ htfs:tag_Project .
    ?descendant skos:prefLabel ?label .
}
```

##### **ResourceRepository**
SPARQL-based resource CRUD operations.

**Core Entities**:
- **Resource URI**: `htfs:resource_{id}`
- **Type**: `htfs:Resource`
- **Properties**:
  - `htfs:url`: File/directory path
  - `htfs:id`: Numeric ID
  - `htfs:hasTag`: Links to assigned tags

**Key Methods**:

| Method | Implementation |
|--------|-----------------|
| `add_resource(url)` | Allocate ID, create RDF triples |
| `get_resource_id(url)` | SPARQL query: find `htfs:id` by `htfs:url` |
| `add_resource_tags(url, tag_ids)` | Add multiple `htfs:hasTag` relationships |
| `get_resources_by_tag_id(tag_ids)` | Query all resources with given tags |
| `get_resource_ids_containing_url(prefix)` | SPARQL CONTAINS filter for directory moves |
| `update_resource_sub_url(old, new)` | Regex-like replacement for directory renaming |

**Resource Querying SPARQL Example**:
```sparql
# Get all resources tagged with "Project"
SELECT ?url WHERE {
    ?resource a htfs:Resource ;
              htfs:url ?url ;
              htfs:hasTag ?tag .
    ?tag skos:broader* htfs:tag_Project .
}
```

---

### 5. **Query Engine (QueryEvaluator.py)**

Compiles user-friendly tag expressions into executable SPARQL queries.

#### Components:

##### **Tokenizer**
Converts string expressions into tokens.

**Token Types**:
- Operators: `&` (AND), `|` (OR), `~` (NOT)
- Grouping: `(`, `)`
- Operands: Tag names (alphanumeric)

**Example**:
```
Input:  "(proj1|proj2)&research&~draft"
Tokens: ['(', 'proj1', '|', 'proj2', ')', '&', 'research', '&', '~', 'draft']
```

##### **Parser**
Builds Abstract Syntax Tree (AST) using operator precedence.

**Operator Precedence** (lowest to highest):
1. OR (`|`)
2. AND (`&`)
3. NOT (`~`)
4. Atoms (parenthesized expressions, tag names)

**Example AST**:
```
Expression: "(proj1|proj2)&research&~draft"

        &
       / \
      &   ~
     / \   \
    |   research  draft
   / \
proj1 proj2
```

##### **ASTEvaluator**
Compiles AST into single SPARQL query.

**Compilation Strategy**:

1. **Operand (`tag`)**: 
   ```sparql
   ?resource htfs:hasTag ?tag1 .
   ?tag1 skos:broader* htfs:tag_projname .
   ```

2. **AND (`&`)**:
   Concatenate pattern clauses (implicit AND)

3. **OR (`|`)**:
   ```sparql
   { pattern1 } UNION { pattern2 }
   ```

4. **NOT (`~`)**:
   ```sparql
   FILTER NOT EXISTS { pattern }
   ```

**Example SPARQL Output**:
```sparql
SELECT DISTINCT ?url WHERE {
    ?resource a htfs:Resource ;
              htfs:url ?url .
    
    # AND clause 1: ?resource has tag proj1 or proj2
    { 
        ?resource htfs:hasTag ?tag1 .
        ?tag1 skos:broader* htfs:tag_proj1 .
    } UNION {
        ?resource htfs:hasTag ?tag2 .
        ?tag2 skos:broader* htfs:tag_proj2 .
    }
    
    # AND clause 2: ?resource has tag research
    ?resource htfs:hasTag ?tag3 .
    ?tag3 skos:broader* htfs:tag_research .
    
    # AND clause 3: NOT draft
    FILTER NOT EXISTS {
        ?resource htfs:hasTag ?tag4 .
        ?tag4 skos:broader* htfs:tag_draft .
    }
}
```

---

### 6. **Filesystem Integration (tagfs_inotify_daemon.py)**

Optional daemon for automatic resource tracking on filesystem changes.

#### Key Class: `TagfsInotifyDaemon`

**Purpose**: Monitor filesystem for moves/renames and update metadata automatically.

**Dependencies**: `inotify` (Linux only)

**Supported Events**:
- `IN_MOVED_FROM`: File/directory started moving
- `IN_MOVED_TO`: File/directory completed move
- `IN_ISDIR`: Event target is a directory

**Implementation**:
- Uses `inotify.adapters.InotifyTree` to watch tagfs boundary
- Maintains event queue indexed by inotify cookie
- On `MOVED_FROM`: Record original path
- On `MOVED_TO`: Match cookie and update resource URL

**Operations**:
- **File Move**: Update single resource URL
- **Directory Move**: Update all resources with matching URL prefix

**Example Event Handling**:
```
MOVED_FROM: /data/project1/doc.pdf (cookie=12345)
    ↓ Store in event queue
MOVED_TO: /data/project2/doc.pdf (cookie=12345)
    ↓ Match cookie, retrieve original
    ↓ th_utils.move_resource("/data/project1/doc.pdf", "/data/project2/doc.pdf")
```

---

### 7. **Data Migration (migrate_sql_to_rdf.py)**

One-time migration utility from SQLite to RDF format.

#### Legacy Schema Mapping:
- `TAGS.ID` & `TAGS.TAGNAME` → `skos:Concept` with `skos:prefLabel`
- `TAGLINKS.TAGID/TAGPARENTID` → `skos:broader` relationship
- `RESOURCES.ID` & `RESOURCES.URL` → `htfs:Resource` with `htfs:url`
- `RESOURCELINKS.RESID/TAGID` → `htfs:hasTag` relationship

#### Process:
1. Read SQLite database
2. Create RDF graph with HTFS/SKOS namespaces
3. Transform each table into RDF triples
4. Preserve ID sequences in metadata
5. Serialize to Turtle format

---

## Data Model & Ontology

### RDF Ontology Definition

#### Namespaces:
```turtle
@prefix htfs: <http://htfs.example.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

#### Classes:

**skos:Concept** (from SKOS vocabulary)
- Represents tags in a controlled vocabulary
- Supports hierarchical relationships

**htfs:Resource**
- Represents tracked files and directories
- Contains filesystem metadata

#### Properties:

| Property | Domain | Range | Purpose |
|----------|--------|-------|---------|
| `skos:prefLabel` | `skos:Concept` | `xsd:string` | Tag display name |
| `skos:broader` | `skos:Concept` | `skos:Concept` | Parent tag (inverse: `skos:narrower`) |
| `htfs:id` | `skos:Concept` ∪ `htfs:Resource` | `xsd:integer` | Numeric identifier |
| `htfs:url` | `htfs:Resource` | `xsd:string` | Filesystem path (relative to boundary) |
| `htfs:hasTag` | `htfs:Resource` | `skos:Concept` | Tag assignment |
| `htfs:maxTagId` | `htfs:meta` | `xsd:integer` | Metadata: highest tag ID |
| `htfs:maxResourceId` | `htfs:meta` | `xsd:integer` | Metadata: highest resource ID |

### Example RDF Graph

```turtle
@prefix htfs: <http://htfs.example.org/ontology#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

# Tags
htfs:tag_Project a skos:Concept ;
    skos:prefLabel "Project" ;
    htfs:id 1 .

htfs:tag_Alpha a skos:Concept ;
    skos:prefLabel "Alpha" ;
    skos:broader htfs:tag_Project ;
    htfs:id 2 .

htfs:tag_Reports a skos:Concept ;
    skos:prefLabel "Reports" ;
    skos:broader htfs:tag_Alpha ;
    htfs:id 3 .

htfs:tag_Research a skos:Concept ;
    skos:prefLabel "Research" ;
    htfs:id 4 .

# Resources
htfs:resource_1 a htfs:Resource ;
    htfs:url "reports/alpha_q1_2026.pdf" ;
    htfs:id 1 ;
    htfs:hasTag htfs:tag_Reports ;
    htfs:hasTag htfs:tag_Research .

htfs:resource_2 a htfs:Resource ;
    htfs:url "reports/beta_draft.pdf" ;
    htfs:id 2 ;
    htfs:hasTag htfs:tag_Reports .

# Metadata
htfs:meta htfs:maxTagId 4 ;
    htfs:maxResourceId 2 .
```

### Tag Hierarchy Semantics

**Broader/Narrower Relationships**:
- `skos:broader` indicates a parent relationship
- `skos:narrower` (inverse) indicates child relationship
- Used for transitive closure queries with `skos:broader+`

**Hierarchy Example**:
```
Project (1)
  ├── Alpha (2)
  │     └── Reports (3)
  └── Beta (5)
        └── Planning (6)

Research (4)  [Independent branch]
```

**Query: Find all resources tagged with "Project"**
- Returns resources directly tagged with `Project`
- Returns resources tagged with `Alpha`, `Beta`, `Reports`, or `Planning` (descendants)
- Due to transitive closure: `skos:broader*`

---

## API & Interfaces

### Python API

#### TagService Interface
```python
from TagService import TagService

# Initialize
ts = TagService(".tagfs.ttl")
ts.initialize()

# Tag operations
ts.add_tag("Project")
tag_id = ts.get_tag_id("Project")
ts.link_tag("Alpha", "Project")  # Alpha is child of Project

# Resource operations
res_id = ts.add_resource("reports/result.pdf")
ts.add_resource_tags("reports/result.pdf", ["Reports", "Research"])
tags = ts.get_resource_tags("reports/result.pdf")
resources = ts.get_resources_by_tag(["Project"])
```

#### QueryEvaluator Interface
```python
from QueryEvaluator import QueryEvaluator

qe = QueryEvaluator(ts)
results = qe.evaluate("(proj1|proj2)&research&~draft")
# Returns list of resource URLs matching expression
```

#### Utilities Interface
```python
from TagfsUtilities import TagfsTagHandlerUtilities, get_tag_fs_boundary

# Auto-detect tagfs boundary
boundary = get_tag_fs_boundary()

# High-level utilities
utils = TagfsTagHandlerUtilities(boundary)
utils.add_tags(["Project/Alpha/Reports"])  # Hierarchical create
resources = utils.get_resources_by_tag_expr("(proj1|proj2)&research")
```

### Command-Line Interface

```bash
# Initialize
tagfs init

# Tag management
tagfs addtags Project Alpha Beta
tagfs addtags "Project/Alpha/Reports"  # Creates hierarchy
tagfs linktags Research Project
tagfs lstags
tagfs renametag Alpha Alpha_v1

# Resource management
tagfs addresource /data/file.pdf
tagfs tagresource /data/file.pdf Reports Research
tagfs getresourcetags /data/file.pdf
tagfs lsresources "(proj1|proj2)&research"

# Filesystem operations
tagfs mvresource /data/file.pdf /data/new/file.pdf
tagfs rmresource /data/file.pdf

# Utilities
tagfs getboundary
tagfs help
```

---

## Query Processing Pipeline

### End-to-End Query Execution

#### Example: `lsresources "(proj1|proj2)&research&~draft"`

**Step 1: Tokenization** (QueryEvaluator.Tokenizer)
```
Input:  "(proj1|proj2)&research&~draft"
Output: ['(', 'proj1', '|', 'proj2', ')', '&', 'research', '&', '~', 'draft']
```

**Step 2: Parsing** (QueryEvaluator.Parser)
```
Output: AST
        &
       / \
      &   ~
     / \   \
    |   research   draft
   / \
proj1 proj2
```

**Step 3: SPARQL Compilation** (QueryEvaluator.ASTEvaluator)
```
_compile(AST) generates:
├─ ?resource htfs:hasTag ?tag1 .
│  ?tag1 skos:broader* htfs:tag_proj1 .
├─ UNION { ?resource htfs:hasTag ?tag2 .
│          ?tag2 skos:broader* htfs:tag_proj2 . }
├─ ?resource htfs:hasTag ?tag3 .
│  ?tag3 skos:broader* htfs:tag_research .
└─ FILTER NOT EXISTS { ?resource htfs:hasTag ?tag4 .
                       ?tag4 skos:broader* htfs:tag_draft . }
```

**Step 4: Query Execution** (GraphManager)
```sparql
SELECT DISTINCT ?url WHERE {
    ?resource a htfs:Resource ;
              htfs:url ?url .
    
    { ?resource htfs:hasTag ?tag1 .
      ?tag1 skos:broader* htfs:tag_proj1 . }
    UNION
    { ?resource htfs:hasTag ?tag2 .
      ?tag2 skos:broader* htfs:tag_proj2 . }
    
    ?resource htfs:hasTag ?tag3 .
    ?tag3 skos:broader* htfs:tag_research .
    
    FILTER NOT EXISTS {
        ?resource htfs:hasTag ?tag4 .
        ?tag4 skos:broader* htfs:tag_draft .
    }
}
```

**Step 5: Result Processing** (TagfsUtilities)
- Convert relative URLs to absolute paths
- Apply tagfs boundary
- Return filesystem paths

---

## Storage & Persistence

### File Format: Turtle (RDF/Turtle)

**Location**: `.tagfs.ttl` in tagfs boundary directory

**Advantages**:
- Human-readable text format
- Supports RDF semantics natively
- Direct compatibility with rdflib
- Easily Git-tracked (text-based)

### Serialization

**GraphManager._save()**:
```python
def _save(self):
    if self.graph is not None:
        self.graph.serialize(destination=self.ttl_path, format="turtle")
```

**When Triggered**:
- After tag creation, linking, or renaming
- After resource creation, deletion, or URL update
- After resource-tag relationship changes
- Explicit `close()` call

### Data Integrity

**Atomic Operations**:
- Each repository method loads graph, modifies, saves atomically
- Graph modifications queued in memory
- Serialized when `_save()` called

**Consistency**:
- ID counters (`maxTagId`, `maxResourceId`) prevent collisions
- SPARQL queries ensure referential integrity
- RDF format prevents unknown properties

### Backup & Recovery

**Recommendations**:
- Version control `.tagfs.ttl` with Git
- Backup before major operations
- Original SQLite `.tagfs.db` preserved for migration reference

---

## Design Patterns

### 1. **Repository Pattern**

**Implementation**: TagRepository, ResourceRepository

**Benefit**: Abstracts RDF/SPARQL details from business logic

**Structure**:
```python
class TagRepository:
    def __init__(self, graph_manager):
        self.gm = graph_manager
        self.g = graph_manager.graph
    
    def add_tag(self, tag_name):
        # SPARQL + RDF operations
        self._save()
```

### 2. **Facade Pattern**

**Implementation**: TagService

**Benefit**: Simplifies API by combining multiple repositories

```python
class TagService:
    def __init__(self, db_path):
        self.db_manager = GraphManager(db_path)
        self.tag_repo = TagRepository(self.db_manager)
        self.resource_repo = ResourceRepository(self.db_manager)
```

### 3. **Compiler Pattern**

**Implementation**: QueryEvaluator.ASTEvaluator

**Benefit**: Parses user input → intermediate representation → executable query

```
Expression → Tokenizer → Parser → AST → Compiler → SPARQL → Executor
```

### 4. **Command Pattern**

**Implementation**: tagfs.py command handlers

**Benefit**: Decouples command parsing from execution

```python
COMMANDS = {
    'init': _init_tag_fs,
    'addtags': _add_tags,
    'lsresources': _get_resources_by_tag_expr,
    # ...
}

def tagfs(args):
    handler = COMMANDS[args.command]
    return handler(args)
```

### 5. **Observer Pattern** (Optional)

**Implementation**: tagfs_inotify_daemon.py

**Benefit**: Monitors filesystem and reacts to changes

```
FileSystem Events → Inotify → Event Queue → Handler → TagfsUtilities
```

### 6. **Context Manager Pattern**

**Implementation**: GraphManager

**Benefit**: Automatic resource cleanup

```python
with GraphManager(db_path) as gm:
    gm.connect()
    # Use graph
    gm.close()  # Automatic on exit
```

---

## Use Cases & Workflows

### Use Case 1: Research Paper Organization

**Scenario**: Organizing research papers across overlapping categories

**Tags Hierarchy**:
```
Science/
  ├─ Biology/
  │    ├─ Genetics/
  │    └─ Ecology/
  ├─ Physics/
  │    └─ Quantum/
  └─ Chemistry/

Status/
  ├─ ToRead
  ├─ Reading
  └─ Completed

Year/
  ├─ 2024
  ├─ 2025
  └─ 2026
```

**Operations**:

```bash
# Setup
tagfs init
tagfs addtags "Science/Biology/Genetics"
tagfs addtags "Science/Physics/Quantum"
tagfs addtags "Status/ToRead" "Status/Reading" "Status/Completed"
tagfs addtags "Year/2024" "Year/2025" "Year/2026"

# Add resources
tagfs addresource ~/papers/crispr_2025.pdf
tagfs addresource ~/papers/quantum_entanglement_2024.pdf

# Tag resources
tagfs tagresource ~/papers/crispr_2025.pdf Genetics Reading 2025
tagfs tagresource ~/papers/quantum_entanglement_2024.pdf Quantum ToRead 2024

# Queries
tagfs lsresources "Science&2025"                    # Papers in 2025 under Science
tagfs lsresources "(Genetics|Quantum)&~ToRead"     # Physics/Biology papers being read/completed
tagfs lsresources "Science&(Reading|Completed)"    # Currently reading/read science papers
```

### Use Case 2: Project File Management

**Scenario**: Managing files for overlapping projects with different phases

**Tags Hierarchy**:
```
Project/
  ├─ ProjectAlpha
  │    ├─ Design
  │    ├─ Development
  │    └─ Testing
  └─ ProjectBeta
       ├─ Planning
       └─ Implementation

Visibility/
  ├─ Internal
  └─ Client

Status/
  ├─ Active
  ├─ OnHold
  └─ Archived
```

**Operations**:

```bash
# Setup
tagfs addtags "Project/ProjectAlpha/Design"
tagfs addtags "Project/ProjectAlpha/Development"
tagfs addtags "Project/ProjectBeta/Planning"

tagfs linktags Visibility/Internal Project
tagfs linktags Visibility/Client Project

# Tagging files
tagfs tagresource ./docs/alpha_spec.pdf ProjectAlpha Design Internal Active
tagfs tagresource ./code/beta_prototype.py ProjectBeta Planning OnHold

# Queries
tagfs lsresources "Project&Active"                     # All active project files
tagfs lsresources "(ProjectAlpha|ProjectBeta)&~OnHold" # Files from both projects, not on hold
tagfs lsresources "ProjectAlpha&(Design|Development)"  # Alpha design and dev files
```

### Use Case 3: Automatic Filesystem Event Tracking

**Scenario**: Daemon-based automatic tagging on file moves

```bash
# Start daemon in background
tagfs_inotify_daemon.py /my/data &

# Manually tag once
tagfs addresource /my/data/important.pdf
tagfs tagresource /my/data/important.pdf ImportantDocs

# Move file - daemon automatically updates URL
mv /my/data/important.pdf /my/data/archive/important.pdf
# Database updated to: archive/important.pdf

# Move directory - all contained resources updated
mv /my/data/project_files/ /my/data/completed/project_files/
# All resources with "project_files/*" paths updated accordingly
```

---

## Performance Considerations

### Query Performance

**Factors Affecting Speed**:

1. **Graph Size**: Number of triples
   - Linear growth with tags and resources
   - Typically manageable for < 100k resources

2. **Query Complexity**: Expression structure
   - AND/OR clauses multiply SPARQL patterns
   - Transitive closure (`skos:broader+`) may be expensive

3. **Materialization vs. Computation**:
   - Currently: Computed on-the-fly (no caching)
   - Could optimize: Pre-compute tag closures

### Optimization Techniques

**1. ID-based Lookups**:
- Numeric IDs used internally for efficiency
- SPARQL filters by `htfs:id` faster than string comparisons

**2. SPARQL UNION Patterns**:
- OR operations use UNION (standard SPARQL optimization)
- Allows query planner to optimize each branch

**3. Graph Indexing**:
- rdflib maintains indexes on predicates
- `skos:broader`, `htfs:hasTag` heavily indexed

**4. Future Optimizations**:
- Materialized tag closure table (computed periodically)
- Prefix indexing on URLs (for `CONTAINS` queries)
- Query result caching

### Scalability Limits

| Metric | Capacity | Notes |
|--------|----------|-------|
| Tags | 10k-100k | Manageable with efficient SPARQL |
| Resources | 1M+ | Limited by RDF triple count |
| Relationships | N/A | Graph remains sparse (DAG structure) |
| Query Response | < 1s | For typical 100-1000 resource result sets |

**Scaling Strategy**:
- Current design suitable for personal/team workflows
- For enterprise scale (millions): Consider RDF triple stores (Virtuoso, Fuseki)

---

## Future Extensions

### 1. **Web Service API**

Expose functionality over REST/GraphQL:

```
POST /api/tags
GET  /api/tags/{id}
POST /api/resources/{id}/tags
GET  /api/search?expr=(proj1|proj2)&status=active
```

### 2. **Tag Inference & Auto-tagging**

- Machine learning on file content (NLP for documents)
- Automatic suggestions based on naming patterns
- Template-based auto-tagging on directory structure

### 3. **Advanced Query Language**

- Temporal queries: `tag@date(YYYY-MM-DD)`
- Numeric ranges: `year:[2020..2025]`
- Metadata filters: `size:>1MB&mimetype:PDF`

### 4. **Visualization & Reporting**

- Tag hierarchy graph visualization
- Resource distribution by tag
- Query result statistics

### 5. **Multi-User & Concurrency**

- Distributed metadata store (Git-based)
- Conflict resolution for tag changes
- Role-based access control

### 6. **External Integration**

- Email client plugin (tag received attachments)
- File manager integration (context menu tagging)
- Document management system connector
- Backup service metadata tagging

### 7. **Performance Scaling**

- Triple store backend (RDF DB)
- Query caching layer
- Materialized views for common queries
- Full-text search integration

### 8. **Enhanced Metadata**

- Tag descriptions and documentation
- Resource annotations (comments)
- Tag versioning and change history
- Resource access patterns and metrics

---

## Conclusion

HTFS represents an innovative approach to filesystem organization by **decoupling taxonomy from hierarchy**. By leveraging RDF and SPARQL, it provides:

✅ **Flexibility**: Multiple categorization schemes simultaneously
✅ **Power**: Complex queries through boolean expressions
✅ **Simplicity**: Intuitive CLI for everyday usage
✅ **Portability**: Text-based storage, Git-friendly
✅ **Extensibility**: Ontology-based design enables future enhancements

The system balances **semantic richness** (RDF/SKOS ontology) with **practical usability** (CLI interface), making it suitable for researchers, data professionals, and anyone needing advanced file organization.

---

## Appendices

### A. Configuration Reference

**Environment Variables**:
- `TAGFS_DB`: Override default `.tagfs.ttl` location

### B. Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (database not initialized, invalid arguments, etc.) |

### C. Dependencies

- **rdflib** (>= 6.0): RDF graph management
- **inotify** (optional): Filesystem event monitoring (Linux only)

### D. File Formats

**Supported**:
- RDF Turtle (`.ttl`)

**Legacy** (via migration):
- SQLite (`.db`) → converted to RDF

### E. SPARQL Vocabulary Reference

**SKOS (Simple Knowledge Organization System)**:
- `skos:Concept`: Tagged concept/category
- `skos:prefLabel`: Preferred display label
- `skos:broader`: Parent concept
- `skos:narrower`: Child concept (inverse)

**HTFS Custom Vocabulary**:
- `htfs:Resource`: Tracked file/directory
- `htfs:id`: Numeric identifier
- `htfs:url`: File path
- `htfs:hasTag`: Tag assignment
- `htfs:maxTagId`: Metadata counter
- `htfs:maxResourceId`: Metadata counter

---

**Document Generated**: March 2026
**System Version**: HTFS-SPARQL v1.0
**For Updates & Issues**: See repository documentation
