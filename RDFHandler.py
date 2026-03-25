import os
import logging
from rdflib import Graph, Namespace, Literal, URIRef, RDF
from rdflib.namespace import SKOS, XSD

logobj = logging.getLogger(__name__)

HTFS = Namespace("http://htfs.example.org/ontology#")


class GraphManager:
    """Wraps an rdflib Graph, handles load/save of .tagfs.ttl."""

    def __init__(self, ttl_path):
        self.ttl_path = ttl_path
        self.graph = None

    def connect(self):
        if self.graph is None:
            self.graph = Graph()
            self.graph.bind("htfs", HTFS)
            self.graph.bind("skos", SKOS)
            if os.path.exists(self.ttl_path):
                self.graph.parse(self.ttl_path, format="turtle")
        return self.graph

    def close(self):
        if self.graph is not None:
            self._save()
            self.graph = None

    def _save(self):
        if self.graph is not None:
            self.graph.serialize(destination=self.ttl_path, format="turtle")

    def initialize_schema(self):
        self.connect()
        meta = HTFS.meta
        if (meta, HTFS.maxTagId, None) not in self.graph:
            self.graph.add((meta, HTFS.maxTagId, Literal(0, datatype=XSD.integer)))
        if (meta, HTFS.maxResourceId, None) not in self.graph:
            self.graph.add((meta, HTFS.maxResourceId, Literal(0, datatype=XSD.integer)))
        self._save()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TagRepository:
    """SPARQL-based tag CRUD using SKOS vocabulary."""

    def __init__(self, graph_manager: GraphManager):
        self.gm = graph_manager
        self.g = graph_manager.graph

    def _tag_uri(self, tag_name):
        return HTFS[f"tag_{tag_name}"]

    def _next_tag_id(self):
        meta = HTFS.meta
        max_id = 0
        for o in self.g.objects(meta, HTFS.maxTagId):
            max_id = int(o)
        new_id = max_id + 1
        self.g.remove((meta, HTFS.maxTagId, None))
        self.g.add((meta, HTFS.maxTagId, Literal(new_id, datatype=XSD.integer)))
        return new_id

    def get_tag_id(self, tag_name) -> int:
        tag_uri = self._tag_uri(tag_name)
        for o in self.g.objects(tag_uri, HTFS.id):
            return int(o)
        return -1

    def get_tag_name(self, tag_id) -> str:
        query = """
        SELECT ?label WHERE {
            ?tag a skos:Concept ;
                 htfs:id ?id ;
                 skos:prefLabel ?label .
            FILTER(?id = ?target_id)
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS, "skos": SKOS},
            initBindings={"target_id": Literal(tag_id, datatype=XSD.integer)},
        )
        for row in results:
            return str(row.label)
        return ""

    def get_tag_list(self) -> list:
        query = """
        SELECT ?label WHERE {
            ?tag a skos:Concept ;
                 skos:prefLabel ?label ;
                 htfs:id ?id .
            FILTER(?id > 0)
        }
        """
        results = self.g.query(query, initNs={"htfs": HTFS, "skos": SKOS})
        return [str(row.label) for row in results]

    def add_tag(self, tag_name) -> bool:
        if self.get_tag_id(tag_name) > 0:
            return False
        new_id = self._next_tag_id()
        tag_uri = self._tag_uri(tag_name)
        self.g.add((tag_uri, RDF.type, SKOS.Concept))
        self.g.add((tag_uri, SKOS.prefLabel, Literal(tag_name)))
        self.g.add((tag_uri, HTFS.id, Literal(new_id, datatype=XSD.integer)))
        self.gm._save()
        return True

    def rename_tag(self, tag_name, new_tag_name) -> bool:
        if self.get_tag_id(new_tag_name) > 0:
            return False
        tag_id = self.get_tag_id(tag_name)
        if tag_id < 0:
            return False

        old_uri = self._tag_uri(tag_name)
        new_uri = self._tag_uri(new_tag_name)

        triples_as_subject = list(self.g.triples((old_uri, None, None)))
        triples_as_object = list(self.g.triples((None, None, old_uri)))

        for s, p, o in triples_as_subject:
            self.g.remove((s, p, o))
        for s, p, o in triples_as_object:
            self.g.remove((s, p, o))

        for _, p, o in triples_as_subject:
            if p == SKOS.prefLabel:
                self.g.add((new_uri, p, Literal(new_tag_name)))
            else:
                self.g.add((new_uri, p, o))
        for s, p, _ in triples_as_object:
            self.g.add((s, p, new_uri))

        self.gm._save()
        return True

    def link_tag(self, tag_name, tag_parent_name) -> bool:
        child_id = self.get_tag_id(tag_name)
        parent_id = self.get_tag_id(tag_parent_name)
        if child_id < 0 or parent_id < 0:
            logobj.error("tags not in db")
            return False
        child_uri = self._tag_uri(tag_name)
        parent_uri = self._tag_uri(tag_parent_name)
        self.g.add((child_uri, SKOS.broader, parent_uri))
        self.gm._save()
        return True

    def unlink_tag(self, tag_name, tag_parent_name) -> bool:
        child_id = self.get_tag_id(tag_name)
        parent_id = self.get_tag_id(tag_parent_name)
        if child_id < 0 or parent_id < 0:
            logobj.error("tags not in db")
            return False
        child_uri = self._tag_uri(tag_name)
        parent_uri = self._tag_uri(tag_parent_name)
        self.g.remove((child_uri, SKOS.broader, parent_uri))
        self.gm._save()
        return True

    def get_parent_tags_by_id(self, tag_id) -> list:
        tag_name = self.get_tag_name(tag_id)
        if not tag_name:
            return []
        tag_uri = self._tag_uri(tag_name)
        result = []
        for parent_uri in self.g.objects(tag_uri, SKOS.broader):
            for pid in self.g.objects(parent_uri, HTFS.id):
                result.append(int(pid))
        return result

    def get_parent_tags(self, tag_name) -> list:
        tag_uri = self._tag_uri(tag_name)
        result = []
        for parent_uri in self.g.objects(tag_uri, SKOS.broader):
            for label in self.g.objects(parent_uri, SKOS.prefLabel):
                result.append(str(label))
        return result

    def get_child_tags_by_id(self, tag_id) -> list:
        tag_name = self.get_tag_name(tag_id)
        if not tag_name:
            return []
        tag_uri = self._tag_uri(tag_name)
        result = []
        for child_uri in self.g.subjects(SKOS.broader, tag_uri):
            for cid in self.g.objects(child_uri, HTFS.id):
                result.append(int(cid))
        return result

    def get_child_tags(self, tag_name) -> list:
        tag_uri = self._tag_uri(tag_name)
        result = []
        for child_uri in self.g.subjects(SKOS.broader, tag_uri):
            for label in self.g.objects(child_uri, SKOS.prefLabel):
                result.append(str(label))
        return result

    def get_downstream_tags_by_id(self, tag_id) -> list:
        tag_name = self.get_tag_name(tag_id)
        if not tag_name:
            return []
        tag_uri = self._tag_uri(tag_name)
        query = """
        SELECT ?id WHERE {
            ?descendant skos:broader+ ?ancestor .
            ?descendant htfs:id ?id .
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS, "skos": SKOS},
            initBindings={"ancestor": tag_uri},
        )
        return [int(row.id) for row in results]

    def get_downstream_tags(self, tag_name) -> list:
        tag_uri = self._tag_uri(tag_name)
        query = """
        SELECT ?label WHERE {
            ?descendant skos:broader+ ?ancestor .
            ?descendant skos:prefLabel ?label .
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS, "skos": SKOS},
            initBindings={"ancestor": tag_uri},
        )
        return [str(row.label) for row in results]

    def get_tag_closure(self, tags: list[str]) -> list[str]:
        closure = []
        for tag in tags:
            tag_id = self.get_tag_id(tag)
            if tag_id < 0:
                logobj.warning("tag %s not present in the db", tag)
                continue
            closure.append(tag)
            closure.extend(self.get_downstream_tags(tag))
        return list(set(closure))


class ResourceRepository:
    """SPARQL-based resource CRUD."""

    def __init__(self, graph_manager: GraphManager):
        self.gm = graph_manager
        self.g = graph_manager.graph

    def _res_uri(self, res_id):
        return HTFS[f"resource_{res_id}"]

    def _next_resource_id(self):
        meta = HTFS.meta
        max_id = 0
        for o in self.g.objects(meta, HTFS.maxResourceId):
            max_id = int(o)
        new_id = max_id + 1
        self.g.remove((meta, HTFS.maxResourceId, None))
        self.g.add((meta, HTFS.maxResourceId, Literal(new_id, datatype=XSD.integer)))
        return new_id

    def add_resource(self, resource_url) -> int:
        new_id = self._next_resource_id()
        res_uri = self._res_uri(new_id)
        self.g.add((res_uri, RDF.type, HTFS.Resource))
        self.g.add((res_uri, HTFS.url, Literal(resource_url)))
        self.g.add((res_uri, HTFS.id, Literal(new_id, datatype=XSD.integer)))
        self.gm._save()
        return new_id

    def get_resource_id(self, resource_url) -> int:
        query = """
        SELECT ?id WHERE {
            ?res a htfs:Resource ;
                 htfs:url ?url ;
                 htfs:id ?id .
            FILTER(?url = ?target_url)
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS},
            initBindings={"target_url": Literal(resource_url)},
        )
        for row in results:
            return int(row.id)
        return -1

    def get_resource_url(self, res_id) -> str:
        res_uri = self._res_uri(res_id)
        for o in self.g.objects(res_uri, HTFS.url):
            return str(o)
        return ""

    def get_resource_ids(self) -> list:
        query = """
        SELECT ?id WHERE {
            ?res a htfs:Resource ;
                 htfs:id ?id .
            FILTER(?id > 0)
        }
        """
        results = self.g.query(query, initNs={"htfs": HTFS})
        return [int(row.id) for row in results]

    def update_resource_url_by_id(self, resource_id, resource_url):
        res_uri = self._res_uri(resource_id)
        self.g.remove((res_uri, HTFS.url, None))
        self.g.add((res_uri, HTFS.url, Literal(resource_url)))
        self.gm._save()

    def update_resource_url(self, resource_url, new_resource_url):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return
        self.update_resource_url_by_id(res_id, new_resource_url)

    def update_resource_sub_url(self, sub_resource_url, update_url):
        res_ids = self.get_resource_ids_containing_url(sub_resource_url)
        for res_id in res_ids:
            url = self.get_resource_url(res_id)
            url = url.replace(sub_resource_url, update_url, 1)
            self.update_resource_url_by_id(res_id, url)

    def get_resource_ids_containing_url(self, sub_resource_url) -> list:
        query = """
        SELECT ?id WHERE {
            ?res a htfs:Resource ;
                 htfs:url ?url ;
                 htfs:id ?id .
            FILTER(CONTAINS(?url, ?sub_url))
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS},
            initBindings={"sub_url": Literal(sub_resource_url)},
        )
        return [int(row.id) for row in results]

    def del_resource(self, resource_url):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.warning("resource not tracked")
            return
        self.del_all_resource_tags(res_id)
        res_uri = self._res_uri(res_id)
        self.g.remove((res_uri, None, None))
        self.gm._save()

    def del_all_resource_tags(self, resource_id):
        res_uri = self._res_uri(resource_id)
        self.g.remove((res_uri, HTFS.hasTag, None))
        self.gm._save()

    def get_resource_tags_by_id(self, resource_id) -> list:
        res_uri = self._res_uri(resource_id)
        result = []
        for tag_uri in self.g.objects(res_uri, HTFS.hasTag):
            for tid in self.g.objects(tag_uri, HTFS.id):
                result.append(int(tid))
        return result

    def get_resource_tags(self, resource_url) -> list:
        res_id = self.get_resource_id(resource_url)
        return self.get_resource_tags_by_id(res_id)

    def add_resource_tag_by_id(self, resource_id, tag_id):
        current_tags = self.get_resource_tags_by_id(resource_id)
        if tag_id not in current_tags:
            res_uri = self._res_uri(resource_id)
            tag_name = self._get_tag_name_by_id(tag_id)
            if tag_name:
                tag_uri = HTFS[f"tag_{tag_name}"]
                self.g.add((res_uri, HTFS.hasTag, tag_uri))
                self.gm._save()

    def _get_tag_name_by_id(self, tag_id) -> str:
        query = """
        SELECT ?label WHERE {
            ?tag a skos:Concept ;
                 htfs:id ?id ;
                 skos:prefLabel ?label .
            FILTER(?id = ?target_id)
        }
        """
        results = self.g.query(
            query,
            initNs={"htfs": HTFS, "skos": SKOS},
            initBindings={"target_id": Literal(tag_id, datatype=XSD.integer)},
        )
        for row in results:
            return str(row.label)
        return ""

    def get_resources_by_tag_id(self, tag_ids) -> list:
        resource_ids = set()
        for tid in tag_ids:
            tag_name = self._get_tag_name_by_id(tid)
            if not tag_name:
                continue
            tag_uri = HTFS[f"tag_{tag_name}"]
            for res_uri in self.g.subjects(HTFS.hasTag, tag_uri):
                for rid in self.g.objects(res_uri, HTFS.id):
                    resource_ids.add(int(rid))
        return list(resource_ids)

    def del_resource_tag_by_id(self, resource_id, tag_id):
        current_tags = self.get_resource_tags_by_id(resource_id)
        if tag_id in current_tags:
            res_uri = self._res_uri(resource_id)
            tag_name = self._get_tag_name_by_id(tag_id)
            if tag_name:
                tag_uri = HTFS[f"tag_{tag_name}"]
                self.g.remove((res_uri, HTFS.hasTag, tag_uri))
                self.gm._save()

    def add_resource_tags(self, resource_url, tag_ids):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return []
        unsuccessful_tags = []
        for tag_id in tag_ids:
            if tag_id > 0:
                self.add_resource_tag_by_id(res_id, tag_id)
            else:
                unsuccessful_tags.append(tag_id)
        return unsuccessful_tags

    def del_resource_tags(self, resource_url, tag_ids):
        res_id = self.get_resource_id(resource_url)
        if res_id < 0:
            logobj.error("resource not tracked")
            return
        for tag_id in tag_ids:
            if tag_id > 0:
                self.del_resource_tag_by_id(res_id, tag_id)
            else:
                logobj.error("tag not in db")
