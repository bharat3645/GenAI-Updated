import { useState, useEffect } from 'react';
import { FileText, Network, Briefcase, Search, Database, TrendingUp } from 'lucide-react';
import { apiGetStats } from '../lib/api';

interface DashboardProps {
  onNavigate: (page: string) => void;
}

const features = [
  {
    id: 'pdf-chat',
    title: 'Multi-PDF Chat',
    description: 'Upload and chat with multiple PDF documents using advanced RAG technology',
    icon: FileText,
    color: 'blue',
  },
  {
    id: 'graphrag',
    title: 'GraphRAG',
    description: 'Extract entities and build knowledge graphs for enhanced document analysis',
    icon: Network,
    color: 'green',
  },
  {
    id: 'resume-feedback',
    title: 'Resume Feedback',
    description: 'Get AI-powered ATS scoring and feedback on your resume',
    icon: Briefcase,
    color: 'orange',
  },
  {
    id: 'research',
    title: 'Research Assistant',
    description: 'Autonomous AI research agent for comprehensive information gathering',
    icon: Search,
    color: 'purple',
  },
  {
    id: 'text-to-sql',
    title: 'Text to SQL',
    description: 'Convert natural language queries into SQL and execute them',
    icon: Database,
    color: 'red',
  },
];

const colorClasses = {
  blue: 'bg-blue-50 text-blue-600 hover:bg-blue-100',
  green: 'bg-green-50 text-green-600 hover:bg-green-100',
  orange: 'bg-orange-50 text-orange-600 hover:bg-orange-100',
  purple: 'bg-purple-50 text-purple-600 hover:bg-purple-100',
  red: 'bg-red-50 text-red-600 hover:bg-red-100',
};

export default function Dashboard({ onNavigate }: DashboardProps) {
  const [stats, setStats] = useState({ documents: 0, reports: 0, queries: 0 });

  useEffect(() => {
    apiGetStats()
      .then(setStats)
      .catch(() => {
        // Gateway may not be running yet — keep defaults
      });
  }, []);

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome to GenAI Platform</h1>
        <p className="text-gray-600">
          Advanced AI-powered platform for document processing, research, and data analysis
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Total Documents</span>
            <TrendingUp className="w-4 h-4 text-green-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">{stats.documents}</div>
          <p className="text-xs text-gray-500 mt-1">PDFs processed</p>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Research Reports</span>
            <TrendingUp className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">{stats.reports}</div>
          <p className="text-xs text-gray-500 mt-1">Reports generated</p>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">SQL Queries</span>
            <TrendingUp className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-3xl font-bold text-gray-900">{stats.queries}</div>
          <p className="text-xs text-gray-500 mt-1">Queries executed</p>
        </div>
      </div>

      <div className="mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Features</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <button
              key={feature.id}
              onClick={() => onNavigate(feature.id)}
              className="bg-white rounded-xl p-6 border border-gray-200 hover:border-gray-300 hover:shadow-lg transition-all text-left group"
            >
              <div
                className={`w-12 h-12 rounded-lg ${colorClasses[feature.color as keyof typeof colorClasses]
                  } flex items-center justify-center mb-4 transition-all`}
              >
                <Icon className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
                {feature.title}
              </h3>
              <p className="text-sm text-gray-600 mb-4">{feature.description}</p>
              <div className="flex items-center justify-end">
                <span className="text-blue-600 text-sm font-medium group-hover:translate-x-1 transition-transform">
                  Launch →
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
