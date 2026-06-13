"""
Local Graph Search Tools Service
Encapsulates graph search, node reading, edge queries, etc. for Report Agent use
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.locale import get_locale, t
from .local_graph import LocalGraphSearch, get_graph_store, NodeData, EdgeData

logger = get_logger('mirofish.local_tools')


@dataclass
class SearchResult:
    """Search result"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        text_parts = [f"Search query: {self.query}", f"Found {self.total_count} relevant items"]
        
        if self.facts:
            text_parts.append("\n### Relevant Facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node information"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "Unknown")
        return f"Entity: {self.name} (Type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge information"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
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
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relationship: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "Unknown"
            invalid_at = self.invalid_at or "Present"
            base_text += f"\nValidity: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Expired: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        return self.invalid_at is not None


class LocalToolsService:
    """
    Local Graph Search Tools Service
    
    Core search tools:
    1. quick_search - Simple search (fast retrieval)
    2. get_all_nodes - Get all graph nodes
    3. get_all_edges - Get all graph edges
    4. get_node_detail - Get detailed node information
    5. get_node_edges - Get edges connected to a node
    6. get_entities_by_type - Get entities by type
    7. get_entity_summary - Get entity relationship summary
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.graph_store = get_graph_store()
        self._llm_client = llm_client
        logger.info("LocalToolsService initialized")
    
    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph semantic search using keyword matching
        
        Args:
            graph_id: Graph ID
            query: Search query
            limit: Maximum results
            scope: "edges" or "nodes"
            
        Returns:
            SearchResult
        """
        logger.info(f"Searching graph {graph_id} for: {query[:50]}")
        
        try:
            graph_search = LocalGraphSearch(self.graph_store)
            results = graph_search.search(
                graph_id=graph_id,
                query=query,
                limit=limit,
                scope=scope
            )
            
            return SearchResult(
                facts=results.get("facts", []),
                edges=results.get("edges", []),
                nodes=results.get("nodes", []),
                query=query,
                total_count=len(results.get("facts", [])) + len(results.get("nodes", []))
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchResult(
                facts=[],
                edges=[],
                nodes=[],
                query=query,
                total_count=0
            )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """Get all nodes in the graph"""
        try:
            nodes = self.graph_store.get_all_nodes(graph_id)
            return [
                NodeInfo(
                    uuid=n.uuid,
                    name=n.name,
                    labels=n.labels,
                    summary=n.summary,
                    attributes=n.attributes
                )
                for n in nodes
            ]
        except Exception as e:
            logger.error(f"Failed to get nodes: {e}")
            return []
    
    def get_all_edges(self, graph_id: str) -> List[EdgeInfo]:
        """Get all edges in the graph"""
        try:
            edges = self.graph_store.get_all_edges(graph_id)
            return [
                EdgeInfo(
                    uuid=e.uuid,
                    name=e.name,
                    fact=e.fact,
                    source_node_uuid=e.source_node_uuid,
                    target_node_uuid=e.target_node_uuid,
                    created_at=e.created_at,
                    valid_at=e.valid_at,
                    invalid_at=e.invalid_at,
                    expired_at=e.expired_at
                )
                for e in edges
            ]
        except Exception as e:
            logger.error(f"Failed to get edges: {e}")
            return []
    
    def get_node_detail(self, graph_id: str, node_uuid: str) -> Optional[NodeInfo]:
        """Get detailed information about a specific node"""
        try:
            node = self.graph_store.get_node(graph_id, node_uuid)
            if node:
                return NodeInfo(
                    uuid=node.uuid,
                    name=node.name,
                    labels=node.labels,
                    summary=node.summary,
                    attributes=node.attributes
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get node detail: {e}")
            return None
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """Get all edges connected to a node"""
        try:
            edges = self.graph_store.get_node_edges(graph_id, node_uuid)
            return [
                EdgeInfo(
                    uuid=e.uuid,
                    name=e.name,
                    fact=e.fact,
                    source_node_uuid=e.source_node_uuid,
                    target_node_uuid=e.target_node_uuid,
                    created_at=e.created_at,
                    valid_at=e.valid_at,
                    invalid_at=e.invalid_at,
                    expired_at=e.expired_at
                )
                for e in edges
            ]
        except Exception as e:
            logger.error(f"Failed to get node edges: {e}")
            return []
    
    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a specific type"""
        try:
            graph_search = LocalGraphSearch(self.graph_store)
            return graph_search.search_by_entity_type(
                graph_id=graph_id,
                entity_type=entity_type,
                enrich_with_edges=True
            )
        except Exception as e:
            logger.error(f"Failed to get entities by type: {e}")
            return []
    
    def get_filtered_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get filtered entities from the graph"""
        try:
            graph_search = LocalGraphSearch(self.graph_store)
            return graph_search.get_filtered_entities(
                graph_id=graph_id,
                defined_entity_types=defined_entity_types,
                enrich_with_edges=True
            )
        except Exception as e:
            logger.error(f"Failed to get filtered entities: {e}")
            return {
                "entities": [],
                "entity_types": [],
                "total_count": 0,
                "filtered_count": 0
            }
    
    def get_graph_stats(self, graph_id: str) -> Dict[str, Any]:
        """Get graph statistics"""
        try:
            return self.graph_store.get_graph_stats(graph_id)
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"error": str(e)}
