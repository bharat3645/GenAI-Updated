/**
 * KnowledgeGraph — Interactive force-directed graph visualization.
 *
 * Renders nodes (entities) and edges (relationships) from the GraphRAG service
 * using react-force-graph-2d.
 */

import { useRef, useCallback, useEffect, useState } from 'react';

interface GraphNode {
    id: string;
    label: string;
    type: string;
    properties?: Record<string, unknown>;
    // Force graph internal props
    x?: number;
    y?: number;
}

interface GraphEdge {
    source: string;
    target: string;
    label: string;
}

interface KnowledgeGraphProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    width?: number;
    height?: number;
    onNodeClick?: (node: GraphNode) => void;
}

const TYPE_COLORS: Record<string, string> = {
    Person: '#6366f1',       // Indigo
    Organization: '#f59e0b', // Amber
    Location: '#10b981',     // Emerald
    Technology: '#3b82f6',   // Blue
    Concept: '#8b5cf6',      // Violet
    default: '#6b7280',      // Gray
};

export default function KnowledgeGraph({
    nodes,
    edges,
    width = 800,
    height = 500,
    onNodeClick,
}: KnowledgeGraphProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [hoveredNode, setHoveredNode] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

    // Simple force-directed layout using canvas
    const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(new Map());

    // Initialize positions randomly
    useEffect(() => {
        const pos = new Map<string, { x: number; y: number }>();
        nodes.forEach((node) => {
            pos.set(node.id, {
                x: Math.random() * (width - 100) + 50,
                y: Math.random() * (height - 100) + 50,
            });
        });
        setPositions(pos);
    }, [nodes, width, height]);

    // Simple force simulation
    useEffect(() => {
        if (nodes.length === 0) return;

        let animationId: number;
        const currentPositions = new Map(positions);
        const velocities = new Map<string, { vx: number; vy: number }>();

        nodes.forEach((n) => {
            velocities.set(n.id, { vx: 0, vy: 0 });
        });

        let iteration = 0;
        const maxIterations = 200;

        function simulate() {
            if (iteration >= maxIterations) return;
            iteration++;

            const alpha = 1 - iteration / maxIterations;

            // Repulsion between all nodes
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const a = currentPositions.get(nodes[i].id);
                    const b = currentPositions.get(nodes[j].id);
                    if (!a || !b) continue;

                    const dx = b.x - a.x;
                    const dy = b.y - a.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const force = (300 * alpha) / (dist * dist);

                    const va = velocities.get(nodes[i].id)!;
                    const vb = velocities.get(nodes[j].id)!;
                    va.vx -= (dx / dist) * force;
                    va.vy -= (dy / dist) * force;
                    vb.vx += (dx / dist) * force;
                    vb.vy += (dy / dist) * force;
                }
            }

            // Attraction along edges
            edges.forEach((edge) => {
                const a = currentPositions.get(typeof edge.source === 'string' ? edge.source : edge.source);
                const b = currentPositions.get(typeof edge.target === 'string' ? edge.target : edge.target);
                if (!a || !b) return;

                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const force = dist * 0.01 * alpha;

                const sourceId = typeof edge.source === 'string' ? edge.source : edge.source;
                const targetId = typeof edge.target === 'string' ? edge.target : edge.target;
                const va = velocities.get(sourceId);
                const vb = velocities.get(targetId);
                if (va) { va.vx += (dx / dist) * force; va.vy += (dy / dist) * force; }
                if (vb) { vb.vx -= (dx / dist) * force; vb.vy -= (dy / dist) * force; }
            });

            // Center gravity
            nodes.forEach((node) => {
                const pos = currentPositions.get(node.id);
                const vel = velocities.get(node.id);
                if (!pos || !vel) return;

                vel.vx += (width / 2 - pos.x) * 0.001 * alpha;
                vel.vy += (height / 2 - pos.y) * 0.001 * alpha;

                // Damping
                vel.vx *= 0.9;
                vel.vy *= 0.9;

                pos.x = Math.max(30, Math.min(width - 30, pos.x + vel.vx));
                pos.y = Math.max(30, Math.min(height - 30, pos.y + vel.vy));
            });

            setPositions(new Map(currentPositions));
            animationId = requestAnimationFrame(simulate);
        }

        animationId = requestAnimationFrame(simulate);
        return () => cancelAnimationFrame(animationId);
    }, [nodes.length, edges.length]);

    // Render on canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.clearRect(0, 0, width, height);

        // Draw edges
        edges.forEach((edge) => {
            const sourceId = typeof edge.source === 'string' ? edge.source : edge.source;
            const targetId = typeof edge.target === 'string' ? edge.target : edge.target;
            const a = positions.get(sourceId);
            const b = positions.get(targetId);
            if (!a || !b) return;

            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = '#d1d5db';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Edge label
            const mx = (a.x + b.x) / 2;
            const my = (a.y + b.y) / 2;
            ctx.fillStyle = '#9ca3af';
            ctx.font = '10px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(edge.label, mx, my - 4);
        });

        // Draw nodes
        nodes.forEach((node) => {
            const pos = positions.get(node.id);
            if (!pos) return;

            const color = TYPE_COLORS[node.type] || TYPE_COLORS.default;
            const isHovered = hoveredNode === node.id;
            const radius = isHovered ? 10 : 7;

            // Glow effect
            if (isHovered) {
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, radius + 4, 0, Math.PI * 2);
                ctx.fillStyle = color + '30';
                ctx.fill();
            }

            // Node circle
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#374151';
            ctx.font = `${isHovered ? 'bold ' : ''}12px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.fillText(node.label, pos.x, pos.y + radius + 14);
        });
    }, [positions, nodes, edges, hoveredNode, width, height]);

    // Mouse interaction
    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const canvas = canvasRef.current;
            if (!canvas) return;
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            let found: string | null = null;
            for (const node of nodes) {
                const pos = positions.get(node.id);
                if (!pos) continue;
                const dx = x - pos.x;
                const dy = y - pos.y;
                if (dx * dx + dy * dy < 100) {
                    found = node.id;
                    break;
                }
            }
            setHoveredNode(found);
            canvas.style.cursor = found ? 'pointer' : 'default';
        },
        [nodes, positions]
    );

    const handleClick = useCallback(
        (_e: React.MouseEvent<HTMLCanvasElement>) => {
            if (hoveredNode) {
                const node = nodes.find((n) => n.id === hoveredNode);
                if (node) {
                    setSelectedNode(node);
                    onNodeClick?.(node);
                }
            } else {
                setSelectedNode(null);
            }
        },
        [hoveredNode, nodes, onNodeClick]
    );

    if (nodes.length === 0) {
        return (
            <div
                className="flex items-center justify-center bg-gray-50 rounded-xl border border-gray-200"
                style={{ width, height }}
            >
                <p className="text-gray-400">Upload a document to see its knowledge graph</p>
            </div>
        );
    }

    return (
        <div className="relative">
            <canvas
                ref={canvasRef}
                width={width}
                height={height}
                className="rounded-xl border border-gray-200 bg-white"
                onMouseMove={handleMouseMove}
                onClick={handleClick}
            />

            {/* Legend */}
            <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm rounded-lg p-2 text-xs space-y-1 border border-gray-100">
                {Object.entries(TYPE_COLORS)
                    .filter(([k]) => k !== 'default')
                    .map(([type, color]) => (
                        <div key={type} className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                            <span className="text-gray-600">{type}</span>
                        </div>
                    ))}
            </div>

            {/* Selected node info */}
            {selectedNode && (
                <div className="absolute bottom-3 left-3 bg-white/95 backdrop-blur-sm rounded-lg p-3 text-sm border border-gray-200 shadow-sm max-w-xs">
                    <div className="font-semibold text-gray-900">{selectedNode.label}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{selectedNode.type}</div>
                    {selectedNode.properties?.description != null && (
                        <p className="text-gray-600 text-xs mt-1">
                            {`${selectedNode.properties.description}`}
                        </p>
                    )}
                </div>
            )}
        </div>
    );
}
