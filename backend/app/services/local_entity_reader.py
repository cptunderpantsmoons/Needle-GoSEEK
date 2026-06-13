"""
Local Entity Reader Service
Replaces ZepEntityReader for reading entities from local graph
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from .local_graph import get_graph_store, NodeData, EdgeData


@dataclass
class EntityNode:
    """实体节点数据结构"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """获取实体类型（排除默认的 Entity 标签）"""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """过滤后的实体集合"""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class LocalEntityReader:
    """
    本地图谱实体读取与过滤服务
    从本地图谱中读取节点，筛选出符合预定义实体类型的节点
    """
    
    def __init__(self):
        self.graph_store = get_graph_store()
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有节点"""
        nodes = self.graph_store.get_all_nodes(graph_id)
        
        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": node.uuid,
                "name": node.name,
                "labels": node.labels,
                "summary": node.summary,
                "attributes": node.attributes,
            })
        
        return nodes_data
    
    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """获取图谱的所有边"""
        edges = self.graph_store.get_all_edges(graph_id)
        
        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": edge.uuid,
                "name": edge.name,
                "fact": edge.fact,
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes,
            })
        
        return edges_data
    
    def filter_defined_entities(
        self, 
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        筛选出符合预定义实体类型的节点
        
        筛选逻辑：
        - 如果节点的 Labels 只有一个"Entity"，说明这个实体不符合我们预定义的类型，跳过
        - 如果节点的 Labels 包含除"Entity"和"Node"之外的标签，说明符合预定义类型，保留
        """
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        node_map = {n["uuid"]: n for n in all_nodes}
        
        filtered_entities = []
        entity_types_found = set()
        
        for node in all_nodes:
            labels = node.get("labels", [])
            
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]
            
            if not custom_labels:
                continue
            
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]
            
            entity_types_found.add(entity_type)
            
            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            
            if enrich_with_edges:
                related_edges = []
                related_node_uuids = set()
                
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "outgoing",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "target_node_uuid": edge["target_node_uuid"],
                        })
                        related_node_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append({
                            "direction": "incoming",
                            "edge_name": edge["name"],
                            "fact": edge["fact"],
                            "source_node_uuid": edge["source_node_uuid"],
                        })
                        related_node_uuids.add(edge["source_node_uuid"])
                
                entity.related_edges = related_edges
                
                related_nodes = []
                for related_uuid in related_node_uuids:
                    if related_uuid in node_map:
                        related_node = node_map[related_uuid]
                        related_nodes.append({
                            "uuid": related_node["uuid"],
                            "name": related_node["name"],
                            "labels": related_node["labels"],
                            "summary": related_node.get("summary", ""),
                        })
                
                entity.related_nodes = related_nodes
            
            filtered_entities.append(entity)
        
        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """获取指定类型的所有实体"""
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities
