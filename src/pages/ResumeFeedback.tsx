import { useState, useRef } from 'react';
import { Upload, FileText, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { atsAnalyze } from '../lib/api';

interface FeedbackResult {
  atsScore: number;
  keywordsFound: string[];
  keywordsMissing: string[];
  strengths: string[];
  improvements: string[];
  formatting: string[];
}

export default function ResumeFeedback() {
  const [file, setFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<FeedbackResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && (selectedFile.type === 'application/pdf' || selectedFile.name.endsWith('.docx'))) {
      setFile(selectedFile);
      setResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!file) return;

    setAnalyzing(true);

    try {
      // Read file content as text
      const text = await file.text();
      const data = await atsAnalyze(text, jobDescription);
      const report = data.report;

      const mappedResult: FeedbackResult = {
        atsScore: report.score || 0,
        keywordsFound: report.keywords_found || [],
        keywordsMissing: report.keywords_missing || [],
        strengths: report.action_verbs_found || [],
        improvements: report.content_suggestions || [],
        formatting: report.formatting_issues || [],
      };

      setResult(mappedResult);
    } catch (error) {
      console.error('ATS analysis failed:', error);
    } finally {
      setAnalyzing(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-orange-600';
    return 'text-red-600';
  };


  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Resume Feedback with ATS Analysis</h1>
        <p className="text-gray-600">
          Get AI-powered feedback and ATS scoring to optimize your resume for applicant tracking systems
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Resume</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Job Description (Optional)
              </label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here for targeted analysis..."
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={4}
              />
              <p className="text-xs text-gray-500 mt-1">
                Adding a job description provides more targeted feedback
              </p>
            </div>

            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-center px-4 py-8 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all"
              >
                <div className="text-center">
                  <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                  <span className="text-sm font-medium text-gray-700 block">
                    Click to upload resume
                  </span>
                  <span className="text-xs text-gray-500 mt-1 block">PDF or DOCX files supported</span>
                </div>
              </button>
            </div>

            {file && (
              <div className="flex items-center justify-between p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-blue-600 mr-3" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-500">
                      {(file.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {analyzing ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    'Analyze Resume'
                  )}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl border border-blue-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h3>
          <div className="space-y-3 text-sm text-gray-700">
            <div className="flex items-start">
              <CheckCircle className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Multi-Agent Analysis</p>
                <p className="text-gray-600 text-xs mt-1">
                  Specialized agents evaluate different aspects
                </p>
              </div>
            </div>
            <div className="flex items-start">
              <CheckCircle className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">ATS Compatibility</p>
                <p className="text-gray-600 text-xs mt-1">
                  Check how well your resume passes ATS systems
                </p>
              </div>
            </div>
            <div className="flex items-start">
              <CheckCircle className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Keyword Analysis</p>
                <p className="text-gray-600 text-xs mt-1">
                  Identify missing and present keywords
                </p>
              </div>
            </div>
            <div className="flex items-start">
              <CheckCircle className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Actionable Feedback</p>
                <p className="text-gray-600 text-xs mt-1">
                  Get specific suggestions for improvement
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {result && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">ATS Score</h2>
              <div
                className={`text-5xl font-bold ${getScoreColor(
                  result.atsScore
                )}`}
              >
                {result.atsScore}
                <span className="text-2xl">/100</span>
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className={`h-4 rounded-full ${result.atsScore >= 80
                  ? 'bg-green-600'
                  : result.atsScore >= 60
                    ? 'bg-orange-600'
                    : 'bg-red-600'
                  }`}
                style={{ width: `${result.atsScore}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 mt-2">
              {result.atsScore >= 80
                ? 'Excellent! Your resume is well-optimized for ATS systems.'
                : result.atsScore >= 60
                  ? 'Good, but there is room for improvement.'
                  : 'Your resume needs significant optimization for ATS systems.'}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center mb-4">
                <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">Keywords Found</h3>
                <span className="ml-auto text-sm text-gray-500">{result.keywordsFound.length}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.keywordsFound.map((keyword, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center mb-4">
                <XCircle className="w-5 h-5 text-red-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">Missing Keywords</h3>
                <span className="ml-auto text-sm text-gray-500">{result.keywordsMissing.length}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {result.keywordsMissing.map((keyword, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-red-100 text-red-700 text-sm rounded-full"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center mb-4">
                <CheckCircle className="w-5 h-5 text-blue-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">Strengths</h3>
              </div>
              <ul className="space-y-2">
                {result.strengths.map((strength, index) => (
                  <li key={index} className="flex items-start text-sm text-gray-700">
                    <span className="w-1.5 h-1.5 bg-blue-600 rounded-full mt-2 mr-2 flex-shrink-0" />
                    {strength}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <div className="flex items-center mb-4">
                <AlertCircle className="w-5 h-5 text-orange-600 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">Improvements</h3>
              </div>
              <ul className="space-y-2">
                {result.improvements.map((improvement, index) => (
                  <li key={index} className="flex items-start text-sm text-gray-700">
                    <span className="w-1.5 h-1.5 bg-orange-600 rounded-full mt-2 mr-2 flex-shrink-0" />
                    {improvement}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center mb-4">
              <FileText className="w-5 h-5 text-purple-600 mr-2" />
              <h3 className="text-lg font-semibold text-gray-900">Formatting Analysis</h3>
            </div>
            <ul className="space-y-2">
              {result.formatting.map((item, index) => (
                <li key={index} className="flex items-start text-sm text-gray-700">
                  <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 mr-2 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
