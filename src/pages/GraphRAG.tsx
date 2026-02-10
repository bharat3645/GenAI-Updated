import { useState } from 'react';
import { Network, Search, Loader2, FileText, ArrowRight } from 'lucide-react';
import { ragQuery } from '../lib/api';

interface Entity {
  id: string;
  name: string;
  type: string;
  description: string;
}

interface Relationship {
  id: string;
  source: string;
  target: string;
  type: string;
}



export default function GraphRAG() {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [answer, setAnswer] = useState('');

  const handleSearch = async () => {
    if (!query.trim() || searching) return;

    setSearching(true);
    setEntities([]);
    setRelationships([]);
    setAnswer('');

    try {
      const data = await ragQuery(query, [], true);

      // Map graph context triples into entities and relationships
      const entityMap = new Map<string, Entity>();
      const rels: Relationship[] = [];

      data.graph_context.forEach((triple, i) => {
        if (!entityMap.has(triple.subject)) {
          entityMap.set(triple.subject, { id: `e_${entityMap.size}`, name: triple.subject, type: 'Concept', description: '' });
        }
        if (!entityMap.has(triple.obj)) {
          entityMap.set(triple.obj, { id: `e_${entityMap.size}`, name: triple.obj, type: 'Concept', description: '' });
        }
        rels.push({ id: `r_${i}`, source: triple.subject, target: triple.obj, type: triple.predicate });
      });

      setEntities(Array.from(entityMap.values()));
      setRelationships(rels);
      setAnswer(data.answer);
      setSearching(false);
    } catch (error) {
      setSearching(false);
      setAnswer(`Error: ${error instanceof Error ? error.message : 'Failed to query. Please try again.'}`);
    }
  };

  const entityTypeColors: Record<string, string> = {
    Technology: 'bg-blue-100 text-blue-700 border-blue-200',
    Concept: 'bg-green-100 text-green-700 border-green-200',
    Field: 'bg-purple-100 text-purple-700 border-purple-200',
    Person: 'bg-orange-100 text-orange-700 border-orange-200',
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">GraphRAG</h1>
        <p className="text-gray-600">
          Extract entities and relationships from documents to build knowledge graphs for enhanced Q&A
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center space-x-2 mb-4">
          <Search className="w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Ask a question to explore the knowledge graph..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleSearch}
            disabled={!query.trim() || searching}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {searching ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Searching...
              </>
            ) : (
              'Search'
            )}
          </button>
        </div>

        {answer && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-blue-900">{answer}</p>
          </div>
        )}
      </div>

      {entities.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center mb-4">
              <Network className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Entities</h2>
              <span className="ml-auto text-sm text-gray-500">{entities.length} found</span>
            </div>

            <div className="space-y-3">
              {entities.map((entity) => (
                <div key={entity.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-gray-900">{entity.name}</h3>
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded border ${entityTypeColors[entity.type] || 'bg-gray-100 text-gray-700 border-gray-200'
                        }`}
                    >
                      {entity.type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{entity.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center mb-4">
              <ArrowRight className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Relationships</h2>
              <span className="ml-auto text-sm text-gray-500">{relationships.length} found</span>
            </div>

            <div className="space-y-3">
              {relationships.map((rel) => (
                <div
                  key={rel.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center">
                    <div className="flex-1 flex items-center">
                      <div className="bg-blue-50 px-3 py-2 rounded-lg">
                        <span className="text-sm font-medium text-blue-900">{rel.source}</span>
                      </div>
                      <div className="mx-3 flex-shrink-0">
                        <ArrowRight className="w-4 h-4 text-gray-400" />
                        <span className="text-xs text-gray-500 block text-center mt-1">
                          {rel.type}
                        </span>
                      </div>
                      <div className="bg-green-50 px-3 py-2 rounded-lg">
                        <span className="text-sm font-medium text-green-900">{rel.target}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Knowledge Graph Visualization</h3>
              <div className="h-48 bg-white border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <Network className="w-12 h-12 text-gray-300 mx-auto mb-2" />
                  <p className="text-sm text-gray-500">
                    Interactive graph visualization
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Entities and relationships mapped
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {entities.length === 0 && !searching && (
        <div className="bg-white rounded-xl border border-gray-200 p-12">
          <div className="text-center">
            <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No Knowledge Graph Data
            </h3>
            <p className="text-gray-600 mb-4">
              Upload documents in the PDF Chat section first, then return here to explore entity
              relationships
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
