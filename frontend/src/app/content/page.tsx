'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { contentAPI } from '@/lib/api';

interface ContentItem {
  id: string;
  title: string;
  source_url: string;
  content_type: string;
  category_hint: string;
  thread_status: string;
  created_at: string;
  extra_data?: any;
}

export default function ContentPage() {
  const router = useRouter();
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const itemsPerPage = 20;

  useEffect(() => {
    loadContents();
  }, [currentPage, statusFilter, typeFilter, categoryFilter]);

  const loadContents = async () => {
    try {
      setLoading(true);
      const offset = (currentPage - 1) * itemsPerPage;
      const result = await contentAPI.listContent({
        limit: itemsPerPage,
        offset,
        status: statusFilter || undefined,
        content_type: typeFilter || undefined,
        category: categoryFilter || undefined,
      });
      setContents(result.items);
      setTotalItems(result.total);
    } catch (error) {
      console.error('Failed to load contents:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredContents = contents.filter(content =>
    content.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPages = Math.ceil(totalItems / itemsPerPage);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published': return 'bg-green-500';
      case 'ready': return 'bg-[#FFD766]';
      case 'analyzing': return 'bg-blue-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'published': return 'Published';
      case 'ready': return 'Ready';
      case 'pending': return 'Pending';
      case 'analyzing': return 'Analyzing';
      case 'failed': return 'Failed';
      default: return status;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50" style={{ fontFamily: 'Pretendard, system-ui, sans-serif' }}>
      {/* Header */}
      <div className="bg-gray-50">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.back()}
                className="p-2 bg-white hover:bg-gray-100 rounded-full transition-colors shadow-sm"
              >
                <svg className="w-5 h-5 text-gray-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div>
                <h1 className="text-2xl font-normal text-gray-900">All Content</h1>
                <p className="text-sm text-gray-600 mt-1">{totalItems} total items</p>
              </div>
            </div>
            <button
              onClick={loadContents}
              className="px-4 py-2 bg-gray-900 text-white rounded-full text-sm hover:bg-gray-800 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-8 pb-8">
        {/* Filters */}
        <div className="bg-white rounded-[24px] p-6 mb-6 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="md:col-span-1">
              <input
                type="text"
                placeholder="Search titles..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-4 py-2 bg-gray-100 rounded-full text-sm text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-[#FFD766] focus:bg-white"
              />
            </div>

            {/* Status Filter */}
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full pl-4 pr-10 py-2 bg-gray-100 rounded-full text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#FFD766] focus:bg-white appearance-none cursor-pointer"
              >
              <option value="">All Status</option>
              <option value="ready">Ready</option>
              <option value="pending">Pending</option>
              <option value="analyzing">Analyzing</option>
              <option value="published">Published</option>
              <option value="failed">Failed</option>
              </select>
              <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* Type Filter */}
            <div className="relative">
              <select
                value={typeFilter}
                onChange={(e) => {
                  setTypeFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full pl-4 pr-10 py-2 bg-gray-100 rounded-full text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#FFD766] focus:bg-white appearance-none cursor-pointer"
              >
              <option value="">All Types</option>
              <option value="model_release">Model Release</option>
              <option value="breaking_news">Breaking News</option>
              <option value="research_paper">Research Paper</option>
              <option value="tool_launch">Tool Launch</option>
              <option value="market_update">Market Update</option>
              <option value="company_news">Company News</option>
              <option value="general">General</option>
              </select>
              <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* Category Filter */}
            <div className="relative">
              <select
                value={categoryFilter}
                onChange={(e) => {
                  setCategoryFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full pl-4 pr-10 py-2 bg-gray-100 rounded-full text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#FFD766] focus:bg-white appearance-none cursor-pointer"
              >
              <option value="">All Categories</option>
              <option value="llm">LLM</option>
              <option value="hardware">Hardware</option>
              <option value="policy">Policy</option>
              <option value="startup">Startup</option>
              <option value="research">Research</option>
              <option value="stock">Stock</option>
              <option value="crypto">Crypto</option>
              <option value="general">General</option>
              </select>
              <svg className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>

        {/* Content List */}
        <div className="bg-white rounded-[24px] shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-gray-500">Loading...</div>
          ) : filteredContents.length === 0 ? (
            <div className="p-12 text-center text-gray-500">No content found</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredContents.map((content) => (
                <div
                  key={content.id}
                  className="p-6 hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/dashboard`)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <div className={`w-2 h-2 rounded-full ${getStatusColor(content.thread_status)}`} />
                        <span className="text-xs font-normal text-gray-500">
                          {getStatusText(content.thread_status)}
                        </span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-500">{content.category_hint}</span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-500">{content.content_type}</span>
                      </div>
                      <h3 className="text-base font-normal text-gray-900 mb-2 line-clamp-2">
                        {content.title}
                      </h3>
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        <span>{new Date(content.created_at).toLocaleDateString()}</span>
                        <a
                          href={content.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-[#FFD766] transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          View Source
                        </a>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/dashboard`);
                      }}
                      className="px-4 py-2 bg-[#FFD766] hover:bg-[#FFD766]/90 rounded-full text-sm font-normal text-gray-900 transition-colors shrink-0"
                    >
                      View
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 border border-gray-200 rounded-full text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
            >
              Previous
            </button>
            <div className="flex items-center gap-2">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum;
                if (totalPages <= 5) {
                  pageNum = i + 1;
                } else if (currentPage <= 3) {
                  pageNum = i + 1;
                } else if (currentPage >= totalPages - 2) {
                  pageNum = totalPages - 4 + i;
                } else {
                  pageNum = currentPage - 2 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`w-10 h-10 rounded-full text-sm transition-colors ${
                      currentPage === pageNum
                        ? 'bg-gray-900 text-white'
                        : 'hover:bg-gray-100 text-gray-700'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-4 py-2 border border-gray-200 rounded-full text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
