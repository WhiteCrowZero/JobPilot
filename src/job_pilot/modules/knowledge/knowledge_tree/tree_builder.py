from __future__ import annotations

from collections import defaultdict

from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.knowledge_tree.tree_snapshot import KnowledgeTreeSnapshotNode
from job_pilot.modules.knowledge.schemas import KnowledgeTreeNode, KnowledgeTreeResponse


class KnowledgeTreeBuilder:
    """知识点树构建器，负责把扁平快照组装为响应树。"""

    def build_tree_groups(
        self,
        *,
        nodes: list[KnowledgeTreeSnapshotNode],
        params: KnowledgeTreeQuery,
    ) -> list[KnowledgeTreeResponse]:
        """按查询入口组装知识点树响应。"""

        sorted_nodes = sorted(
            nodes,
            key=lambda node: (
                node.skill_id,
                node.depth,
                node.parent_id or 0,
                node.sort_order,
                node.id,
            ),
        )
        nodes_by_id = {node.id: node for node in sorted_nodes}
        child_ids_by_parent_id: dict[int, list[int]] = defaultdict(list)
        root_ids_by_skill_id: dict[int, list[int]] = defaultdict(list)
        skill_ids: list[int] = []
        seen_skill_ids: set[int] = set()

        for node in sorted_nodes:
            if node.skill_id not in seen_skill_ids:
                skill_ids.append(node.skill_id)
                seen_skill_ids.add(node.skill_id)

            if node.parent_id is None:
                root_ids_by_skill_id[node.skill_id].append(node.id)
                continue
            child_ids_by_parent_id[node.parent_id].append(node.id)

        if params.root_id is not None:
            root = nodes_by_id.get(params.root_id)
            if root is None:
                return []
            return [
                KnowledgeTreeResponse(
                    skill_id=root.skill_id,
                    tree=[
                        self._build_node(
                            node_id=root.id,
                            nodes_by_id=nodes_by_id,
                            child_ids_by_parent_id=child_ids_by_parent_id,
                            seen=set(),
                        )
                    ],
                )
            ]

        if params.skill_id is not None:
            root_ids = root_ids_by_skill_id.get(params.skill_id, [])
            if not root_ids:
                return []
            return [
                KnowledgeTreeResponse(
                    skill_id=params.skill_id,
                    tree=[
                        self._build_node(
                            node_id=root_id,
                            nodes_by_id=nodes_by_id,
                            child_ids_by_parent_id=child_ids_by_parent_id,
                            seen=set(),
                        )
                        for root_id in root_ids
                    ],
                )
            ]

        return [
            KnowledgeTreeResponse(
                skill_id=skill_id,
                tree=[
                    self._build_node(
                        node_id=root_id,
                        nodes_by_id=nodes_by_id,
                        child_ids_by_parent_id=child_ids_by_parent_id,
                        seen=set(),
                    )
                    for root_id in root_ids_by_skill_id.get(skill_id, [])
                ],
            )
            for skill_id in skill_ids
            if root_ids_by_skill_id.get(skill_id)
        ]

    def _build_node(
        self,
        *,
        node_id: int,
        nodes_by_id: dict[int, KnowledgeTreeSnapshotNode],
        child_ids_by_parent_id: dict[int, list[int]],
        seen: set[int],
    ) -> KnowledgeTreeNode:
        """递归组装响应节点，避免异常环形数据导致无限递归。"""

        node = nodes_by_id[node_id]
        next_seen = seen | {node_id}
        children = [
            self._build_node(
                node_id=child_id,
                nodes_by_id=nodes_by_id,
                child_ids_by_parent_id=child_ids_by_parent_id,
                seen=next_seen,
            )
            for child_id in child_ids_by_parent_id.get(node_id, [])
            if child_id not in next_seen and child_id in nodes_by_id
        ]
        return KnowledgeTreeNode(
            id=node.id,
            title=node.title,
            summary=node.summary,
            level=node.level,
            depth=node.depth,
            sort_order=node.sort_order,
            status=node.status,
            created_at=node.created_at,
            updated_at=node.updated_at,
            children=children,
        )
