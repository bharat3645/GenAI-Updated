import { useState } from 'react';
import { Search, Loader2, FileText, CheckCircle, Clock, XCircle } from 'lucide-react';
import { researchStart } from '../lib/api';

interface ResearchTask {
  id: string;
  query: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  report?: string;
  createdAt: Date;
  completedAt?: Date;
}

export default function ResearchAssistant() {
  const [query, setQuery] = useState('');
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [activeTask, setActiveTask] = useState<ResearchTask | null>(null);

  const handleStartResearch = async () => {
    if (!query.trim()) return;

    const newTask: ResearchTask = {
      id: Date.now().toString(),
      query,
      status: 'processing',
      createdAt: new Date(),
    };

    setTasks((prev) => [newTask, ...prev]);
    const currentQuery = query;
    setQuery('');
    setActiveTask(newTask);

    try {
      const data = await researchStart(currentQuery, 'standard');

      const completedTask: ResearchTask = {
        ...newTask,
        id: data.task_id || newTask.id,
        status: 'completed',
        completedAt: new Date(),
        report: data.report,
      };

      setTasks((prev) => prev.map((t) => (t.id === newTask.id ? completedTask : t)));
      setActiveTask(completedTask);
    } catch (error) {
      const failedTask: ResearchTask = {
        ...newTask,
        status: 'failed',
        completedAt: new Date(),
        report: undefined,
      };

      setTasks((prev) => prev.map((t) => (t.id === newTask.id ? failedTask : t)));
      setActiveTask(failedTask);
    }
  };

  const getStatusIcon = (status: ResearchTask['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-600" />;
    }
  };

  const getStatusColor = (status: ResearchTask['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'processing':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'failed':
        return 'bg-red-100 text-red-700 border-red-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Research Assistant</h1>
        <p className="text-gray-600">
          AI-powered autonomous research agent that gathers and synthesizes information
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Start New Research</h2>
        <div className="flex items-center space-x-2">
          <Search className="w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleStartResearch()}
            placeholder="Enter your research topic or question..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={handleStartResearch}
            disabled={!query.trim()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Start Research
          </button>
        </div>

        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">Example Research Topics:</h3>
          <div className="flex flex-wrap gap-2">
            {[
              'Latest trends in artificial intelligence',
              'Renewable energy technologies comparison',
              'Market analysis of electric vehicles',
              'Impact of remote work on productivity',
            ].map((example) => (
              <button
                key={example}
                onClick={() => setQuery(example)}
                className="px-3 py-1 bg-white text-blue-700 text-sm rounded-full hover:bg-blue-100 transition-colors"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Research History</h2>

          {tasks.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No research tasks yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {tasks.map((task) => (
                <button
                  key={task.id}
                  onClick={() => setActiveTask(task)}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${activeTask?.id === task.id
                      ? 'bg-blue-50 border-blue-200'
                      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                    }`}
                >
                  <div className="flex items-start justify-between mb-1">
                    {getStatusIcon(task.status)}
                    <span
                      className={`text-xs px-2 py-1 rounded border ${getStatusColor(task.status)}`}
                    >
                      {task.status}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 line-clamp-2">{task.query}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {task.createdAt.toLocaleString()}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
          {activeTask ? (
            <>
              <div className="flex items-start justify-between mb-6">
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-gray-900 mb-2">{activeTask.query}</h2>
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <span>Started: {activeTask.createdAt.toLocaleString()}</span>
                    {activeTask.completedAt && (
                      <span>Completed: {activeTask.completedAt.toLocaleString()}</span>
                    )}
                  </div>
                </div>
                <span className={`px-3 py-1 text-sm rounded border ${getStatusColor(activeTask.status)}`}>
                  {activeTask.status}
                </span>
              </div>

              {activeTask.status === 'processing' ? (
                <div className="text-center py-12">
                  <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">Research in Progress</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Our AI agents are gathering and analyzing information...
                  </p>
                  <div className="max-w-md mx-auto space-y-2 text-sm text-left">
                    <div className="flex items-center text-gray-700">
                      <CheckCircle className="w-4 h-4 text-green-600 mr-2" />
                      Planning research strategy
                    </div>
                    <div className="flex items-center text-gray-700">
                      <Loader2 className="w-4 h-4 text-blue-600 mr-2 animate-spin" />
                      Gathering information from sources
                    </div>
                    <div className="flex items-center text-gray-400">
                      <Clock className="w-4 h-4 mr-2" />
                      Analyzing and synthesizing data
                    </div>
                    <div className="flex items-center text-gray-400">
                      <Clock className="w-4 h-4 mr-2" />
                      Generating comprehensive report
                    </div>
                  </div>
                </div>
              ) : activeTask.report ? (
                <div className="prose prose-sm max-w-none">
                  <div className="bg-gray-50 rounded-lg p-6 border border-gray-200">
                    <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700">
                      {activeTask.report}
                    </pre>
                  </div>
                  <div className="mt-4 flex space-x-2">
                    <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm">
                      Export as PDF
                    </button>
                    <button className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors text-sm">
                      Copy to Clipboard
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <XCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">Research Failed</h3>
                  <p className="text-sm text-gray-600">
                    An error occurred while processing this research task.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full py-12">
              <div className="text-center">
                <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No Research Selected
                </h3>
                <p className="text-gray-600">
                  Start a new research task or select one from your history
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
