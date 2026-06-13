"""
Custom In-Memory Graph Implementation
Replaces Zep Cloud API for graph context management

This module provides:
1. Graph data structures (nodes, edges)
2. Graph storage and retrieval
3. Semantic search capabilities
4. Entity filtering and relationship queries

Usage:
    from .local_graph import get_graph_store, get_graph_search
    
    # Get the global graph store
    store = get_graph_store()
    
    # Create a graph
    store.create_graph("my_graph", "My Graph", "Description")
    
    # Add nodes and edges
    from .local_graph import NodeData, EdgeData
    node = NodeData(uuid="uuid1", name="John", labels=["Person"], summary="A person")
    store.add_node("my_graph", node)
    
    # Search
    search = get_graph_search("my_graph")
    results = search.search("my_graph", "query text")
"""

import os
import json
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import re


@dataclass
class NodeData:
    """Node data structure"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeData':
        return cls(
            uuid=data.get("uuid", ""),
            name=data.get("name", ""),
            labels=data.get("labels", []),
            summary=data.get("summary", ""),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class EdgeData:
    """Edge data structure"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    # Time information
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "attributes": self.attributes,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EdgeData':
        return cls(
            uuid=data.get("uuid", ""),
            name=data.get("name", ""),
            fact=data.get("fact", ""),
            source_node_uuid=data.get("source_node_uuid", ""),
            target_node_uuid=data.get("target_node_uuid", ""),
            attributes=data.get("attributes", {}),
            created_at=data.get("created_at"),
            valid_at=data.get("valid_at"),
            invalid_at=data.get("invalid_at"),
            expired_at=data.get("expired_at"),
        )


@dataclass
class GraphMetadata:
    """Graph metadata"""
    graph_id: str
    name: str
    description: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ontology: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "ontology": self.ontology,
        }


class LocalGraphStore:
    """
    Local in-memory graph store with file persistence
    
    Provides:
    1. Node and edge storage
    2. CRUD operations
    3. Search capabilities
    4. Relationship queries
    """
    
    # Storage directory
    GRAPHS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'uploads', 'graphs'
    )
    
    def __init__(self):
        # Ensure storage directory exists
        os.makedirs(self.GRAPHS_DIR, exist_ok=True)
        
        # In-memory cache: graph_id -> {metadata, nodes, edges}
        self._graphs: Dict[str, Dict[str, Any]] = {}
        
        # Load existing graphs from disk
        self._load_all_graphs()
    
    def _get_graph_dir(self, graph_id: str) -> str:
        """Get directory for a specific graph"""
        graph_dir = os.path.join(self.GRAPHS_DIR, graph_id)
        os.makedirs(graph_dir, exist_ok=True)
        return graph_dir
    
    def _load_all_graphs(self):
        """Load all graphs from disk into memory"""
        if not os.path.exists(self.GRAPHS_DIR):
            return
        
        for graph_id in os.listdir(self.GRAPHS_DIR):
            graph_dir = os.path.join(self.GRAPHS_DIR, graph_id)
            if not os.path.isdir(graph_dir):
                continue
            
            try:
                # Load metadata
                meta_file = os.path.join(graph_dir, "metadata.json")
                if os.path.exists(meta_file):
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    # Load nodes
                    nodes = []
                    nodes_file = os.path.join(graph_dir, "nodes.json")
                    if os.path.exists(nodes_file):
                        with open(nodes_file, 'r', encoding='utf-8') as f:
                            nodes_data = json.load(f)
                            nodes = [NodeData.from_dict(n) for n in nodes_data]
                    
                    # Load edges
                    edges = []
                    edges_file = os.path.join(graph_dir, "edges.json")
                    if os.path.exists(edges_file):
                        with open(edges_file, 'r', encoding='utf-8') as f:
                            edges_data = json.load(f)
                            edges = [EdgeData.from_dict(e) for e in edges_data]
                    
                    self._graphs[graph_id] = {
                        "metadata": GraphMetadata(**metadata) if isinstance(metadata, dict) else metadata,
                        "nodes": {n.uuid: n for n in nodes},
                        "edges": {e.uuid: e for e in edges},
                    }
            except Exception as e:
                print(f"Warning: Failed to load graph {graph_id}: {e}")
    
    def create_graph(self, graph_id: str, name: str, description: str = "") -> GraphMetadata:
        """Create a new graph"""
        metadata = GraphMetadata(
            graph_id=graph_id,
            name=name,
            description=description,
        )
        
        self._graphs[graph_id] = {
            "metadata": metadata,
            "nodes": {},
            "edges": {},
        }
        
        # Persist to disk
        self._save_graph(graph_id)
        
        return metadata
    
    def get_graph_metadata(self, graph_id: str) -> Optional[GraphMetadata]:
        """Get graph metadata"""
        if graph_id in self._graphs:
            return self._graphs[graph_id]["metadata"]
        return None
    
    def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
        """Set graph ontology"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        self._graphs[graph_id]["metadata"].ontology = ontology
        self._save_graph(graph_id)
    
    def add_node(self, graph_id: str, node: NodeData) -> NodeData:
        """Add a node to the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        self._graphs[graph_id]["nodes"][node.uuid] = node
        self._save_graph(graph_id)
        
        return node
    
    def add_nodes(self, graph_id: str, nodes: List[NodeData]):
        """Add multiple nodes to the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        for node in nodes:
            self._graphs[graph_id]["nodes"][node.uuid] = node
        
        self._save_graph(graph_id)
    
    def add_edge(self, graph_id: str, edge: EdgeData) -> EdgeData:
        """Add an edge to the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        self._graphs[graph_id]["edges"][edge.uuid] = edge
        self._save_graph(graph_id)
        
        return edge
    
    def add_edges(self, graph_id: str, edges: List[EdgeData]):
        """Add multiple edges to the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        for edge in edges:
            self._graphs[graph_id]["edges"][edge.uuid] = edge
        
        self._save_graph(graph_id)
    
    def get_all_nodes(self, graph_id: str) -> List[NodeData]:
        """Get all nodes in the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        return list(self._graphs[graph_id]["nodes"].values())
    
    def get_all_edges(self, graph_id: str) -> List[EdgeData]:
        """Get all edges in the graph"""
        if graph_id not in self._graphs:
            raise ValueError(f"Graph {graph_id} not found")
        
        return list(self._graphs[graph_id]["edges"].values())
    
    def get_node(self, graph_id: str, node_uuid: str) -> Optional[NodeData]:
        """Get a specific node by UUID"""
        if graph_id not in self._graphs:
            return None
        
        return self._graphs[graph_id]["nodes"].get(node_uuid)
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeData]:
        """Get all edges connected to a node"""
        if graph_id not in self._graphs:
            return []
        
        edges = self._graphs[graph_id]["edges"].values()
        return [e for e in edges if e.source_node_uuid == node_uuid or e.target_node_uuid == node_uuid]
    
    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph"""
        if graph_id not in self._graphs:
            return False
        
        # Remove from memory
        del self._graphs[graph_id]
        
        # Remove from disk
        graph_dir = self._get_graph_dir(graph_id)
        try:
            import shutil
            shutil.rmtree(graph_dir)
        except Exception:
            pass
        
        return True
    
    def _save_graph(self, graph_id: str):
        """Save graph to disk"""
        if graph_id not in self._graphs:
            return
        
        graph_dir = self._get_graph_dir(graph_id)
        data = self._graphs[graph_id]
        
        # Save metadata
        meta_file = os.path.join(graph_dir, "metadata.json")
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(data["metadata"].to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save nodes
        nodes_file = os.path.join(graph_dir, "nodes.json")
        nodes_data = [n.to_dict() for n in data["nodes"].values()]
        with open(nodes_file, 'w', encoding='utf-8') as f:
            json.dump(nodes_data, f, ensure_ascii=False, indent=2)
        
        # Save edges
        edges_file = os.path.join(graph_dir, "edges.json")
        edges_data = [e.to_dict() for e in data["edges"].values()]
        with open(edges_file, 'w', encoding='utf-8') as f:
            json.dump(edges_data, f, ensure_ascii=False, indent=2)
    
    def get_graph_stats(self, graph_id: str) -> Dict[str, Any]:
        """Get graph statistics"""
        if graph_id not in self._graphs:
            return {"error": "Graph not found"}
        
        data = self._graphs[graph_id]
        nodes = list(data["nodes"].values())
        edges = list(data["edges"].values())
        
        # Count entity types
        entity_types = set()
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types.add(label)
        
        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_types": list(entity_types),
        }


class LocalGraphSearch:
    """
    Local graph search implementation
    
    Provides semantic-like search using keyword matching and ranking
    """
    
    def __init__(self, graph_store: LocalGraphStore):
        self.store = graph_store
    
    def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> Dict[str, Any]:
        """
        Search the graph for relevant content
        
        Args:
            graph_id: Graph ID
            query: Search query
            limit: Maximum results
            scope: "edges", "nodes", or "all"
        
        Returns:
            Search results with facts, edges, nodes
        """
        if scope not in ["edges", "nodes", "all"]:
            scope = "edges"
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # Tokenize query
        query_terms = self._tokenize(query)
        
        if scope in ["edges", "all"]:
            edges = self.store.get_all_edges(graph_id)
            scored_edges = []
            
            for edge in edges:
                score = self._score_text(edge.fact, query_terms)
                score += self._score_text(edge.name, query_terms)
                
                if score > 0:
                    scored_edges.append((score, edge))
            
            # Sort by score
            scored_edges.sort(key=lambda x: x[0], reverse=True)
            
            for score, edge in scored_edges[:limit]:
                facts.append(edge.fact)
                edges_result.append(edge.to_dict())
        
        if scope in ["nodes", "all"]:
            nodes = self.store.get_all_nodes(graph_id)
            scored_nodes = []
            
            for node in nodes:
                score = self._score_text(node.name, query_terms)
                score += self._score_text(node.summary, query_terms)
                
                if score > 0:
                    scored_nodes.append((score, node))
            
            scored_nodes.sort(key=lambda x: x[0], reverse=True)
            
            for score, node in scored_nodes[:limit]:
                nodes_result.append(node.to_dict())
        
        return {
            "facts": facts,
            "edges": edges_result,
            "nodes": nodes_result,
            "query": query,
            "total_count": len(facts) + len(nodes_result),
        }
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms"""
        # Simple tokenization: split on whitespace and punctuation
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        # Filter out very short tokens
        return [t for t in tokens if len(t) > 2]
    
    def _score_text(self, text: str, query_terms: List[str]) -> float:
        """Score text relevance to query terms"""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        score = 0.0
        
        for term in query_terms:
            # Exact match
            if term in text_lower:
                score += 2.0
            # Partial match
            elif any(term in word for word in text_lower.split()):
                score += 1.0
        
        return score
    
    def search_by_entity_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all entities of a specific type"""
        nodes = self.store.get_all_nodes(graph_id)
        
        result = []
        for node in nodes:
            # Check if node has the entity type
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if entity_type in custom_labels:
                node_data = node.to_dict()
                
                if enrich_with_edges:
                    edges = self.store.get_node_edges(graph_id, node.uuid)
                    node_data["related_edges"] = [
                        {
                            "direction": "outgoing" if e.source_node_uuid == node.uuid else "incoming",
                            "edge_name": e.name,
                            "fact": e.fact,
                            "target_node_uuid": e.target_node_uuid if e.source_node_uuid == node.uuid else None,
                            "source_node_uuid": e.source_node_uuid if e.target_node_uuid == node.uuid else None,
                        }
                        for e in edges
                    ]
                
                result.append(node_data)
        
        return result
    
    def get_filtered_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> Dict[str, Any]:
        """
        Get filtered entities from the graph
        
        Returns entities that have labels beyond just "Entity" or "Node"
        """
        nodes = self.store.get_all_nodes(graph_id)
        edges = self.store.get_all_edges(graph_id) if enrich_with_edges else []
        
        # Build node map for related node lookup
        node_map = {n.uuid: n for n in nodes}
        
        filtered_entities = []
        entity_types_found = set()
        
        for node in nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                continue
            
            # Filter by defined types if specified
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
            entity_data = node.to_dict()
            
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in edges:
                    if edge.source_node_uuid == node.uuid:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge.name,
                            "fact": edge.fact,
                            "target_node_uuid": edge.target_node_uuid,
                        })
                        related_node_uuids.add(edge.target_node_uuid)
                    elif edge.target_node_uuid == node.uuid:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge.name,
                            "fact": edge.fact,
                            "source_node_uuid": edge.source_node_uuid,
                        })
                        related_node_uuids.add(edge.source_node_uuid)
                
                entity_data["related_edges"] = related_edges
                
                # Get related nodes info
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node.uuid,
                            "name": related_node.name,
                            "labels": related_node.labels,
                            "summary": related_node.summary,
                        })
                
                entity_data["related_nodes"] = related_nodes
            
            filtered_entities.append(entity_data)
        
        return {
            "entities": filtered_entities,
            "entity_types": list(entity_types_found),
            "total_count": len(nodes),
            "filtered_count": len(filtered_entities),
        }


# Global graph store instance
_local_graph_store: Optional[LocalGraphStore] = None


def get_graph_store() -> LocalGraphStore:
    """Get the global graph store instance"""
    global _local_graph_store
    if _local_graph_store is None:
        _local_graph_store = LocalGraphStore()
    return _local_graph_store


def get_graph_search(graph_id: str) -> LocalGraphSearch:
    """Get a search instance for a specific graph"""
    store = get_graph_store()
    return LocalGraphSearch(store)
