import { useState } from 'react';
import { Database, Play, Loader2, Table, History } from 'lucide-react';
import { sqlGenerate, sqlExecute } from '../lib/api';

interface QueryResult {
  query: string;
  sql: string;
  results: any[];
  timestamp: Date;
}

export default function TextToSQL() {
  const [query, setQuery] = useState('');
  const [executing, setExecuting] = useState(false);
  const [currentResult, setCurrentResult] = useState<QueryResult | null>(null);
  const [history, setHistory] = useState<QueryResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleExecuteQuery = async () => {
    if (!query.trim() || executing) return;

    setExecuting(true);
    setError(null);

    try {
      // Step 1: Generate SQL from natural language
      const genData = await sqlGenerate(query);

      if (!genData.safe) {
        setError('The generated SQL was flagged as unsafe and cannot be executed.');
        setCurrentResult({
          query,
          sql: genData.generated_sql,
          results: [],
          timestamp: new Date(),
        });
        setExecuting(false);
        return;
      }

      // Step 2: Execute the generated SQL
      const execData = await sqlExecute(genData.generated_sql);

      // Map column/row arrays into objects for the table UI
      const mappedResults = execData.rows.map((row) => {
        const obj: Record<string, unknown> = {};
        execData.columns.forEach((col, i) => {
          obj[col] = (row as unknown[])[i];
        });
        return obj;
      });

      const result: QueryResult = {
        query,
        sql: genData.generated_sql,
        results: mappedResults,
        timestamp: new Date(),
      };

      setCurrentResult(result);
      setHistory((prev) => [result, ...prev].slice(0, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while executing the query.');
    } finally {
      setExecuting(false);
    }
  };

  const exampleQueries = [
    'Show me all users who registered in the last 30 days',
    'Find the top 5 most uploaded document types',
    'Count how many chat sessions were created this month',
    'List users with more than 10 PDF documents',
    'Show average ATS scores by month',
  ];

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Text to SQL</h1>
        <p className="text-gray-600">
          Convert natural language queries into SQL and execute them on the database
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center mb-4">
              <Database className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Database Schema</h2>
            </div>

            <div className="space-y-3 text-sm">
              <div className="border border-gray-200 rounded-lg p-3">
                <h3 className="font-semibold text-gray-900 mb-2">users</h3>
                <ul className="space-y-1 text-xs text-gray-600">
                  <li>• id (uuid)</li>
                  <li>• email (text)</li>
                  <li>• created_at (timestamp)</li>
                </ul>
              </div>

              <div className="border border-gray-200 rounded-lg p-3">
                <h3 className="font-semibold text-gray-900 mb-2">pdf_documents</h3>
                <ul className="space-y-1 text-xs text-gray-600">
                  <li>• id (uuid)</li>
                  <li>• user_id (uuid)</li>
                  <li>• filename (text)</li>
                  <li>• upload_date (timestamp)</li>
                  <li>• processed (boolean)</li>
                </ul>
              </div>

              <div className="border border-gray-200 rounded-lg p-3">
                <h3 className="font-semibold text-gray-900 mb-2">chat_sessions</h3>
                <ul className="space-y-1 text-xs text-gray-600">
                  <li>• id (uuid)</li>
                  <li>• user_id (uuid)</li>
                  <li>• title (text)</li>
                  <li>• created_at (timestamp)</li>
                </ul>
              </div>

              <div className="border border-gray-200 rounded-lg p-3">
                <h3 className="font-semibold text-gray-900 mb-2">resume_feedback</h3>
                <ul className="space-y-1 text-xs text-gray-600">
                  <li>• id (uuid)</li>
                  <li>• user_id (uuid)</li>
                  <li>• ats_score (integer)</li>
                  <li>• created_at (timestamp)</li>
                </ul>
              </div>

              <div className="border border-gray-200 rounded-lg p-3">
                <h3 className="font-semibold text-gray-900 mb-2">research_tasks</h3>
                <ul className="space-y-1 text-xs text-gray-600">
                  <li>• id (uuid)</li>
                  <li>• user_id (uuid)</li>
                  <li>• query (text)</li>
                  <li>• status (text)</li>
                  <li>• created_at (timestamp)</li>
                </ul>
              </div>
            </div>
          </div>

          {history.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center mb-4">
                <History className="w-5 h-5 text-gray-600 mr-2" />
                <h2 className="text-lg font-semibold text-gray-900">History</h2>
              </div>

              <div className="space-y-2">
                {history.slice(0, 5).map((item, index) => (
                  <button
                    key={index}
                    onClick={() => {
                      setQuery(item.query);
                      setCurrentResult(item);
                    }}
                    className="w-full text-left p-2 rounded-lg hover:bg-gray-50 border border-gray-200 transition-colors"
                  >
                    <p className="text-xs text-gray-900 line-clamp-2">{item.query}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {item.timestamp.toLocaleTimeString()}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="lg:col-span-3 space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Natural Language Query</h2>

            <div className="space-y-4">
              <div className="flex items-start space-x-2">
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Describe what data you want to retrieve in plain English..."
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows={3}
                />
                <button
                  onClick={handleExecuteQuery}
                  disabled={!query.trim() || executing}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {executing ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 mr-2" />
                      Execute
                    </>
                  )}
                </button>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">Example Queries:</h3>
                <div className="flex flex-wrap gap-2">
                  {exampleQueries.map((example) => (
                    <button
                      key={example}
                      onClick={() => setQuery(example)}
                      className="px-3 py-1 bg-gray-100 text-gray-700 text-xs rounded-full hover:bg-gray-200 transition-colors"
                    >
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {currentResult && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">Generated SQL</h2>
                  <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                    Copy SQL
                  </button>
                </div>
                <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                  <pre className="text-sm text-green-400 font-mono">{currentResult.sql}</pre>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center">
                    <Table className="w-5 h-5 text-blue-600 mr-2" />
                    <h2 className="text-lg font-semibold text-gray-900">Results</h2>
                  </div>
                  <span className="text-sm text-gray-600">
                    {currentResult.results.length} row{currentResult.results.length !== 1 ? 's' : ''}
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        {currentResult.results.length > 0 &&
                          Object.keys(currentResult.results[0]).map((key) => (
                            <th
                              key={key}
                              className="text-left py-3 px-4 font-semibold text-gray-700 bg-gray-50"
                            >
                              {key}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody>
                      {currentResult.results.map((row, index) => (
                        <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                          {Object.values(row).map((value: any, i) => (
                            <td key={i} className="py-3 px-4 text-gray-900">
                              {value?.toString() || '-'}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 flex space-x-2">
                  <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm">
                    Export as CSV
                  </button>
                  <button className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors text-sm">
                    Export as JSON
                  </button>
                </div>
              </div>
            </>
          )}

          {!currentResult && !executing && (
            <div className="bg-white rounded-xl border border-gray-200 p-12">
              <div className="text-center">
                <Database className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No Query Results Yet
                </h3>
                <p className="text-gray-600">
                  Enter a natural language query above to see SQL generation and results
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
