"""
Local Graph Builder Service
Replaces Zep Cloud API for graph construction

This module provides:
1. Text chunking and processing
2. LLM-based entity and relationship extraction
3. Local graph storage using LocalGraphStore
"""

import os
import uuid
import time
import threading
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from .text_processor import TextProcessor
from ..utils.llm_client import LLMClient
from ..utils.locale import t, get_locale, set_locale
from .local_graph import (
    get_graph_store, NodeData, EdgeData, 
    LocalGraphStore, LocalGraphSearch
)


@dataclass
class GraphInfo:
    """图谱信息"""
    graph_id: str
    node_count: int
    edge_count: int
    entity_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "entity_types": self.entity_types,
        }


class LocalGraphBuilderService:
    """
    本地图谱构建服务
    使用LLM从文本中提取实体和关系，存储到本地图谱
    """
    
    # Entity/Relation extraction prompt template
    EXTRACTION_PROMPT = """You are a knowledge graph extraction expert. Extract entities and relationships from the following text.

Given ontology:
{ontology}

Text to analyze:
{text}

Extract entities and relationships according to the ontology. Return ONLY valid JSON in this exact format:
{{
    "entities": [
        {{
            "name": "Entity Name",
            "type": "EntityType",
            "summary": "Brief description",
            "attributes": {{"attr1": "value1", "attr2": "value2"}}
        }}
    ],
    "relationships": [
        {{
            "source": "Source Entity Name",
            "target": "Target Entity Name",
            "relation_type": "RelationType",
            "fact": "Description of the relationship"
        }}
    ]
}}

Ensure:
1. Entity names match exactly between relationships and entities
2. Only use entity types and relation types from the ontology
3. Include meaningful summaries and attributes
4. Return ONLY the JSON, no other text"""

    def __init__(self):
        self.task_manager = TaskManager()
        self.llm_client = LLMClient()
        self.graph_store = get_graph_store()
    
    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3
    ) -> str:
        """
        异步构建图谱
        
        Args:
            text: 输入文本
            ontology: 本体定义（来自接口 1 的输出）
            graph_name: 图谱名称
            chunk_size: 文本块大小
            chunk_overlap: 块重叠大小
            batch_size: 每批发送的块数量
            
        Returns:
            任务 ID
        """
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            }
        )
        
        current_locale = get_locale()

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap, batch_size, current_locale)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
        locale: str = 'zh'
    ):
        """图谱构建工作线程"""
        set_locale(locale)
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message=t('progress.startBuildingGraph')
            )
            
            graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
            
            self.graph_store.create_graph(graph_id, graph_name, "MiroFish Social Simulation Graph")
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=t('progress.graphCreated', graphId=graph_id)
            )
            
            self.graph_store.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message=t('progress.ontologySet')
            )
            
            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=t('progress.textSplit', count=total_chunks)
            )
            
            all_entities = {}
            all_relationships = []
            
            for i, chunk in enumerate(chunks):
                batch_num = i // batch_size + 1
                total_batches = (total_chunks + batch_size - 1) // batch_size
                
                self.task_manager.update_task(
                    task_id,
                    progress=20 + int((i / total_chunks) * 40),
                    message=t('progress.sendingBatch', current=batch_num, total=total_batches, chunks=1)
                )
                
                extracted = self._extract_entities_and_relations(chunk, ontology)
                
                if extracted:
                    for entity in extracted.get('entities', []):
                        entity_uuid = hashlib.md5(entity['name'].encode()).hexdigest()
                        if entity_uuid not in all_entities:
                            all_entities[entity_uuid] = entity
                    
                    all_relationships.extend(extracted.get('relationships', []))
                
                if batch_num % batch_size == 0:
                    time.sleep(0.5)
            
            self.task_manager.update_task(
                task_id,
                progress=60,
                message=t('progress.waitingZepProcess')
            )
            
            nodes_to_add = []
            for entity_uuid, entity in all_entities.items():
                entity_types = ontology.get('entity_types', [])
                type_names = [et['name'] for et in entity_types]
                
                labels = ["Entity"]
                if entity.get('type') in type_names:
                    labels.append(entity['type'])
                
                node = NodeData(
                    uuid=entity_uuid,
                    name=entity['name'],
                    labels=labels,
                    summary=entity.get('summary', ''),
                    attributes=entity.get('attributes', {})
                )
                nodes_to_add.append(node)
            
            self.graph_store.add_nodes(graph_id, nodes_to_add)
            
            edges_to_add = []
            entity_name_to_uuid = {e['name']: u for u, e in all_entities.items()}
            
            for rel in all_relationships:
                source_uuid = entity_name_to_uuid.get(rel.get('source'))
                target_uuid = entity_name_to_uuid.get(rel.get('target'))
                
                if source_uuid and target_uuid:
                    edge_uuid = hashlib.md5(f"{source_uuid}_{rel.get('relation_type')}_{target_uuid}".encode()).hexdigest()
                    
                    edge = EdgeData(
                        uuid=edge_uuid,
                        name=rel.get('relation_type', 'related'),
                        fact=rel.get('fact', ''),
                        source_node_uuid=source_uuid,
                        target_node_uuid=target_uuid,
                        attributes={}
                    )
                    edges_to_add.append(edge)
            
            self.graph_store.add_edges(graph_id, edges_to_add)
            
            self.task_manager.update_task(
                task_id,
                progress=90,
                message=t('progress.fetchingGraphInfo')
            )
            
            graph_info = self._get_graph_info(graph_id)
            
            self.task_manager.complete_task(task_id, {
                "graph_id": graph_id,
                "graph_info": graph_info.to_dict(),
                "chunks_processed": total_chunks,
            })
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.task_manager.fail_task(task_id, error_msg)
    
    def _extract_entities_and_relations(
        self, 
        text: str, 
        ontology: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to extract entities and relationships from text"""
        try:
            ontology_str = json.dumps(ontology, ensure_ascii=False)
            
            prompt = self.EXTRACTION_PROMPT.format(
                ontology=ontology_str,
                text=text[:2000]
            )
            
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.strip()
            
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            return None
    
    def _get_graph_info(self, graph_id: str) -> GraphInfo:
        """获取图谱信息"""
        nodes = self.graph_store.get_all_nodes(graph_id)
        edges = self.graph_store.get_all_edges(graph_id)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ["Entity", "Node"]:
                        entity_types.add(label)

        return GraphInfo(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            entity_types=list(entity_types)
        )
    
    def get_graph_data(self, graph_id: str) -> Dict[str, Any]:
        """获取完整图谱数据"""
        nodes = self.graph_store.get_all_nodes(graph_id)
        edges = self.graph_store.get_all_edges(graph_id)

        node_map = {n.uuid: n.name for n in nodes}
        
        nodes_data = [n.to_dict() for n in nodes]
        
        edges_data = []
        for edge in edges:
            edge_dict = edge.to_dict()
            edge_dict["source_node_name"] = node_map.get(edge.source_node_uuid, "")
            edge_dict["target_node_name"] = node_map.get(edge.target_node_uuid, "")
            edges_data.append(edge_dict)
        
        return {
            "graph_id": graph_id,
            "nodes": nodes_data,
            "edges": edges_data,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
        }
    
    def delete_graph(self, graph_id: str):
        """删除图谱"""
        self.graph_store.delete_graph(graph_id)
