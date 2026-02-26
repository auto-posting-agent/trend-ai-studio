"use client"

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { contentAPI, ContentItem, ContentStats, threadsAPI, ThreadsMetrics, ThreadComment, AutoReplyStats, GeneratedPostItem } from "@/lib/api";

export default function Dashboard() {
  const [stats, setStats] = useState<ContentStats | null>(null);
  const [contents, setContents] = useState<ContentItem[]>([]);
  const [processing, setProcessing] = useState<string | null>(null);
  const [selectedContent, setSelectedContent] = useState<ContentItem | null>(null);
  const [generatedPost, setGeneratedPost] = useState<{
    content: string;
    analysis: string;
    webSearch?: string;
  } | null>(null);
  const [editedPosts, setEditedPosts] = useState<string[]>([]);
  const [isEdited, setIsEdited] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [tabBounds, setTabBounds] = useState({ left: 0, width: 0 });
  const [threadMetrics, setThreadMetrics] = useState<ThreadsMetrics | null>(null);
  const [comments, setComments] = useState<ThreadComment[]>([]);
  const [autoReplyStats, setAutoReplyStats] = useState<AutoReplyStats | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);

  // New state for hierarchical view
  const [expandedContents, setExpandedContents] = useState<Set<string>>(new Set());
  const [generatedPosts, setGeneratedPosts] = useState<Record<string, GeneratedPostItem[]>>({});
  const [selectedPost, setSelectedPost] = useState<GeneratedPostItem | null>(null);
  const [editingPostId, setEditingPostId] = useState<string | null>(null);

  const tabRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({});
  const containerRef = useRef<HTMLDivElement | null>(null);

  const tabs = ["Dashboard", "Analytics", "Auto Reply", "Settings"];

  const handleCrawlNow = () => {
    alert('크롤링을 시작합니다. 잠시 후 새로운 콘텐츠가 추가됩니다.');
    // TODO: Implement crawling trigger API
  };

  const handleNewPost = () => {
    alert('새 포스트 작성 기능은 곧 추가됩니다.');
    // TODO: Implement manual post creation
  };

  const handleAnalytics = () => {
    setActiveTab("Analytics");
  };

  const handleAutoReplySettings = () => {
    setActiveTab("Auto Reply");
  };

  useEffect(() => {
    const updateTabBounds = () => {
      const activeButton = tabRefs.current[activeTab];
      const container = containerRef.current;

      if (activeButton && container) {
        const containerRect = container.getBoundingClientRect();
        const buttonRect = activeButton.getBoundingClientRect();

        setTabBounds({
          left: buttonRect.left - containerRect.left,
          width: buttonRect.width,
        });
      }
    };

    updateTabBounds();
    window.addEventListener('resize', updateTabBounds);

    return () => window.removeEventListener('resize', updateTabBounds);
  }, [activeTab]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statsData, contentsData, threadsData, commentsData, autoReplyData] = await Promise.all([
        contentAPI.getStats(),
        contentAPI.listContent({ limit: 20 }),
        threadsAPI.getMetrics().catch(() => null),
        threadsAPI.getComments(undefined, 10).catch(() => ({ data: [], total: 0 })),
        threadsAPI.getAutoReplyStats().catch(() => null)
      ]);
      setStats(statsData);
      setContents(contentsData.items);
      if (threadsData) {
        setThreadMetrics(threadsData);
      }
      setComments(commentsData.data);
      if (autoReplyData) {
        setAutoReplyStats(autoReplyData);
      }
    } catch (error) {
      console.error('Failed to load:', error);
    }
  };

  const handleProcess = async (id: string) => {
    try {
      setProcessing(id);
      const content = contents.find(c => c.id === id);
      setSelectedContent(content || null);

      const result = await contentAPI.processContent(id);

      // Check if GeneratedPost was created (new architecture)
      const generatedPostId = result.generated_post_id;

      if (generatedPostId) {
        // Fetch the generated post
        const postData = await contentAPI.getGeneratedPost(generatedPostId);

        setGeneratedPost({
          content: postData.generated_post,
          analysis: postData.analysis_summary || 'Content analyzed and approved for publishing',
          webSearch: postData.web_search_results || '',
        });
        setEditedPosts([...postData.thread_parts]);
        setIsEdited(false);
        setShowModal(true);
      } else {
        // Handle failed/skipped content
        const detail = await contentAPI.getContent(id);
        const error = detail.extra_data?.error as string;
        const message = error || 'Content generation failed';
        alert(`Content was not generated:\n\n${message}`);
      }

      await loadData();
    } catch (error) {
      console.error('Failed:', error);
      alert('Failed to generate content. Please try again.');
    } finally {
      setProcessing(null);
    }
  };

  const handleSave = async () => {
    if (!selectedContent) return;

    try {
      setIsSaving(true);
      await contentAPI.saveEditedContent(selectedContent.id, editedPosts);

      // UI 업데이트
      if (generatedPost) {
        setGeneratedPost({
          ...generatedPost,
          content: editedPosts.join('\n\n')
        });
      }

      setIsEdited(false);
      alert('저장되었습니다!');
      await loadData();
    } catch (error) {
      console.error('Failed to save:', error);
      alert('저장 실패');
    } finally {
      setIsSaving(false);
    }
  };

  const handlePostEdit = (index: number, newValue: string) => {
    const updated = [...editedPosts];
    updated[index] = newValue;
    setEditedPosts(updated);
    setIsEdited(true);
  };

  const handleApprove = async (id: string) => {
    try {
      setProcessing(id);
      const result = await contentAPI.approveContent(id);
      await loadData();
      setShowModal(false);
      alert(`Successfully published to Threads!\n${result.thread_url || ''}`);
    } catch (error) {
      console.error('Failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to publish to Threads. Please check your API credentials.';
      alert(errorMessage);
    } finally {
      setProcessing(null);
    }
  };

  // New handlers for hierarchical view
  const toggleContent = async (contentId: string) => {
    const newExpanded = new Set(expandedContents);
    if (newExpanded.has(contentId)) {
      newExpanded.delete(contentId);
    } else {
      newExpanded.add(contentId);
      // Fetch generated posts for this content
      try {
        const result = await contentAPI.listGeneratedPosts(contentId);
        setGeneratedPosts(prev => ({
          ...prev,
          [contentId]: result.posts
        }));
      } catch (error) {
        console.error('Failed to load generated posts:', error);
      }
    }
    setExpandedContents(newExpanded);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedPost(null);
    setSelectedContent(null);
    setGeneratedPost(null);
    setEditedPosts([]);
    setIsEdited(false);
    setEditingPostId(null);
  };

  const handleEditPost = (post: GeneratedPostItem) => {
    setSelectedPost(post);
    setEditedPosts([...post.thread_parts]);
    setGeneratedPost({
      content: post.generated_post,
      analysis: post.analysis_summary,
      webSearch: post.web_search_results
    });
    setIsEdited(false);
    setEditingPostId(post.id);
    setShowModal(true);
  };

  const handleSavePost = async () => {
    if (!selectedPost) return;

    try {
      setIsSaving(true);
      await contentAPI.updateGeneratedPost(selectedPost.id, editedPosts);

      // Refresh generated posts for this content
      const result = await contentAPI.listGeneratedPosts(selectedPost.content_id);
      setGeneratedPosts(prev => ({
        ...prev,
        [selectedPost.content_id]: result.posts
      }));

      setIsEdited(false);
      closeModal();
      alert('저장되었습니다!');
    } catch (error) {
      console.error('Failed to save:', error);
      alert('저장 실패');
    } finally {
      setIsSaving(false);
    }
  };

  const handlePublishPost = async (postId: string, contentId: string) => {
    try {
      setProcessing(postId);
      const result = await contentAPI.publishGeneratedPost(postId);

      // Refresh generated posts
      const postsResult = await contentAPI.listGeneratedPosts(contentId);
      setGeneratedPosts(prev => ({
        ...prev,
        [contentId]: postsResult.posts
      }));

      alert(`Successfully published to Threads!\n${result.thread_url || ''}`);
    } catch (error) {
      console.error('Failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to publish';
      alert(errorMessage);
    } finally {
      setProcessing(null);
    }
  };

  const handleDeletePost = async (postId: string, contentId: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;

    try {
      await contentAPI.deleteGeneratedPost(postId);

      // Refresh generated posts
      const result = await contentAPI.listGeneratedPosts(contentId);
      setGeneratedPosts(prev => ({
        ...prev,
        [contentId]: result.posts
      }));

      alert('삭제되었습니다');
    } catch (error) {
      console.error('Failed:', error);
      alert('삭제 실패');
    }
  };

  const totalContents = stats ? Object.values(stats.by_status).reduce((a, b) => a + b, 0) : 0;
  const pendingCount = stats?.by_status.pending || 0;
  const readyCount = stats?.by_status.ready || 0;
  const publishedCount = stats?.by_status.published || 0;

  const totalViews = threadMetrics?.total_views || 0;
  const totalLikes = threadMetrics?.total_likes || 0;
  const totalComments = threadMetrics?.total_comments || 0;
  const avgEngagement = totalViews > 0 ? ((totalLikes + totalComments) / totalViews * 100).toFixed(1) : '0';
  const followers = 0; // Threads API doesn't provide follower count directly

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,#E8E8EA_0%,#F5F3F0_35%,#FFF9E6_100%)]">
      <div className="max-w-[1440px] mx-auto px-10 py-8">
        {/* Navigation */}
        <div className="bg-white/60 backdrop-blur-md rounded-full px-8 py-3 mb-12 flex items-center justify-between shadow-[0_2px_24px_rgba(0,0,0,0.06)]">
          <div className="px-6 py-2 border border-gray-300 rounded-full">
            <span className="text-sm font-light tracking-tight text-gray-900">Trend AI Studio</span>
          </div>

          <div ref={containerRef} className="flex gap-2 relative bg-gray-100/50 rounded-full p-1">
            {tabs.map((tab) => (
              <button
                key={tab}
                ref={(el) => { tabRefs.current[tab] = el }}
                onClick={() => setActiveTab(tab)}
                className={`relative px-6 py-2.5 text-sm font-light transition-colors z-10 ${
                  activeTab === tab ? "text-white" : "text-gray-600 hover:text-gray-900"
                }`}
              >
                {tab}
              </button>
            ))}
            <motion.div
              className="absolute bg-gray-900 rounded-full shadow-sm"
              initial={false}
              animate={{ x: tabBounds.left, width: tabBounds.width }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}
              style={{ height: "calc(100% - 8px)", top: 4 }}
            />
          </div>

          <div className="flex items-center gap-3">
            <motion.button
              onClick={() => setActiveTab("Settings")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="px-4 py-2.5 bg-white/80 hover:bg-white border border-gray-200 rounded-full transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="text-sm font-light text-gray-700">Setting</span>
            </motion.button>
            <div className="relative">
              <motion.button
                onClick={() => setShowNotifications(!showNotifications)}
                whileHover={{ scale: 1.1, rotate: 15 }}
                whileTap={{ scale: 0.9 }}
                className="w-10 h-10 bg-white/80 hover:bg-white border border-gray-200 rounded-full flex items-center justify-center transition-colors relative"
              >
                <svg className="w-4 h-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                {readyCount > 0 && (
                  <div className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                    {readyCount}
                  </div>
                )}
              </motion.button>

              {showNotifications && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-lg border border-gray-200 p-4 z-50"
                >
                  <h3 className="text-sm font-medium text-gray-900 mb-3">알림</h3>
                  {readyCount > 0 ? (
                    <div className="space-y-2">
                      {contents.filter(c => c.thread_status === 'ready').slice(0, 3).map((content) => (
                        <div
                          key={content.id}
                          onClick={() => {
                            setSelectedContent(content);
                            setGeneratedPost({
                              content: content.extra_data?.generated_post as string || '',
                              analysis: content.extra_data?.analysis as string || '',
                              webSearch: content.extra_data?.web_search_results as string,
                            });
                            setShowModal(true);
                            setShowNotifications(false);
                          }}
                          className="p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                        >
                          <p className="text-sm font-medium text-gray-900 truncate">{content.title}</p>
                          <p className="text-xs text-gray-500 mt-1">검토 및 발행 준비 완료</p>
                        </div>
                      ))}
                      {readyCount > 3 && (
                        <p className="text-xs text-gray-500 text-center pt-2">+{readyCount - 3}개 더 보기</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">새로운 알림이 없습니다</p>
                  )}
                </motion.div>
              )}
            </div>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 17 }}
              className="w-10 h-10 bg-gray-900 rounded-full flex items-center justify-center text-white text-sm font-medium shadow-sm"
            >
              T
            </motion.button>
          </div>
        </div>

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-[40px] font-light tracking-tight mb-6 text-gray-900" style={{ fontFamily: 'Pretendard, system-ui, sans-serif', letterSpacing: '-0.025em' }}>Threads Content Dashboard</h1>

          <div className="flex items-center gap-4">
            <div className="flex gap-3">
              <div className="px-5 py-2.5 bg-gray-900 text-white rounded-full">
                <span className="text-sm font-light">Crawled {pendingCount}</span>
              </div>
              <div className="px-5 py-2.5 bg-[#FFD766] text-gray-900 rounded-full">
                <span className="text-sm font-light">Generated {readyCount}</span>
              </div>
              <div className="px-5 py-2.5 bg-green-500 text-white rounded-full">
                <span className="text-sm font-light">Published {publishedCount}</span>
              </div>
            </div>

            <div className="flex-1 relative h-10 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-gray-900 via-[#FFD766] to-green-500 transition-all duration-500"
                style={{ width: `${totalContents > 0 ? (publishedCount / totalContents * 100) : 0}%` }}
              ></div>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-sm font-light text-gray-500">Today</span>
              <div className="px-4 py-2 bg-white border border-gray-300 rounded-full">
                <span className="text-sm font-medium text-gray-900">{stats?.today.total_crawled || 0} new</span>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="flex items-center gap-12 mb-8" style={{ fontFamily: 'Pretendard, system-ui, sans-serif', letterSpacing: '-0.025em' }}>
          <div className="flex items-center gap-4">
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <div className="text-[56px] font-light tracking-tight text-gray-900">{totalViews.toLocaleString()}</div>
            <span className="text-sm font-light text-gray-500 mt-8">Views</span>
          </div>

          <div className="flex items-center gap-4">
            <svg className="w-6 h-6 text-red-400" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
            </svg>
            <div className="text-[56px] font-light tracking-tight text-gray-900">{totalLikes.toLocaleString()}</div>
            <span className="text-sm font-light text-gray-500 mt-8">Likes</span>
          </div>

          <div className="flex items-center gap-4">
            <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
            </svg>
            <div className="text-[56px] font-light tracking-tight text-gray-900">{totalComments.toLocaleString()}</div>
            <span className="text-sm font-light text-gray-500 mt-8">Comments</span>
          </div>
        </div>

        {/* Bento Grid */}
        <div className="grid grid-cols-12 gap-6">
          {/* My Threads Profile */}
          <div className="col-span-4 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.12)] text-white relative overflow-hidden" style={{ fontFamily: 'Pretendard, system-ui, sans-serif', letterSpacing: '-0.025em' }}>
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#FFD766]/10 rounded-full -mr-16 -mt-16"></div>
            <div className="absolute bottom-0 left-0 w-24 h-24 bg-[#FFD766]/5 rounded-full -ml-12 -mb-12"></div>
            <div className="relative z-10">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-16 h-16 bg-[#FFD766] rounded-full flex items-center justify-center text-3xl font-bold text-gray-900">
                  T
                </div>
                <div>
                  <h3 className="text-xl font-light">@{threadMetrics?.profile?.username || 'trendai_studio'}</h3>
                  <p className="text-sm font-normal text-gray-300">스레드 프로필</p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-normal text-gray-300">전체 게시물</span>
                  <span className="text-2xl font-light">{threadMetrics?.total_threads || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-normal text-gray-300">평균 참여도</span>
                  <span className="text-2xl font-light text-[#FFD766]">{avgEngagement}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-normal text-gray-300">발행됨</span>
                  <span className="text-2xl font-light">{publishedCount}</span>
                </div>
              </div>

              <button className="w-full mt-6 px-4 py-3 bg-[#FFD766] hover:bg-[#FFD766]/90 text-gray-900 rounded-full text-sm font-medium transition-colors">
                Threads에서 보기
              </button>
            </div>
          </div>

          {/* Engagement Chart */}
          <div className="col-span-4 bg-white rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.04)]" style={{ fontFamily: 'Pretendard, system-ui, sans-serif', letterSpacing: '-0.025em' }}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-base font-normal text-gray-900">주간 참여도</h3>
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
              </svg>
            </div>

            <div className="mb-6">
              <div className="text-4xl font-light tracking-tight text-gray-900">
                {avgEngagement}%
              </div>
              <div className="text-xs font-normal text-green-600 mt-1">지난 주 대비 +2.4%</div>
            </div>

            <div className="flex items-end justify-between h-32 gap-2">
              {[45, 52, 48, 65, 58, 72, 68].map((height, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-2">
                  <div
                    className="w-full rounded-full"
                    style={{
                      height: `${height}%`,
                      backgroundColor: i === 6 ? '#FFD766' : '#1F1F1F'
                    }}
                  ></div>
                  <span className="text-xs font-light text-gray-400">
                    {['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Auto Reply Status */}
          <div className="col-span-4 bg-white rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.04)]" style={{ fontFamily: 'Pretendard, system-ui, sans-serif', letterSpacing: '-0.025em' }}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-base font-normal text-gray-900">자동 답장</h3>
              <button
                onClick={() => {
                  // TODO: Implement toggle API
                  alert('자동 답장 설정은 Settings 탭에서 변경할 수 있습니다.');
                }}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 ${
                  autoReplyStats?.enabled ? 'bg-gray-900' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    autoReplyStats?.enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-[20px]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-normal text-gray-700">AI 응답</span>
                  <span className="text-lg font-light text-gray-900">{autoReplyStats?.total_replies_today || 0}</span>
                </div>
                <div className="text-xs font-light text-gray-500">Today</div>
              </div>

              <div className="p-4 bg-[#FFD766]/10 rounded-[20px]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-normal text-gray-700">평균 응답 시간</span>
                  <span className="text-lg font-light text-gray-900">
                    {autoReplyStats?.avg_response_time_seconds || 0}s
                  </span>
                </div>
                <div className="text-xs font-normal text-gray-500">
                  {autoReplyStats && autoReplyStats.yesterday_avg_response_time > 0
                    ? `어제 대비 ${autoReplyStats.avg_response_time_seconds - autoReplyStats.yesterday_avg_response_time >= 0 ? '+' : ''}${autoReplyStats.avg_response_time_seconds - autoReplyStats.yesterday_avg_response_time}s`
                    : '데이터 없음'}
                </div>
              </div>

              <button className="w-full px-4 py-3 bg-gray-900 text-white rounded-full text-sm font-normal hover:bg-gray-800 transition-colors">
                자동 답장 설정
              </button>
            </div>
          </div>

          {/* Recent Comments */}
          <div className="col-span-6 bg-white rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-light text-gray-900">Recent Comments</h3>
              <button
                onClick={() => alert('전체 댓글 페이지로 이동합니다. (곧 구현 예정)')}
                className="text-sm font-light text-gray-500 hover:text-gray-900"
              >
                View All
              </button>
            </div>

            <div className="space-y-4">
              {comments.length === 0 ? (
                <div className="text-center py-8 text-gray-500 font-light">
                  No comments yet
                </div>
              ) : (
                comments.slice(0, 4).map((comment) => (
                  <div key={comment.id} className="flex items-start gap-3 p-3 hover:bg-gray-50 rounded-[16px] transition-colors">
                    <div className="w-10 h-10 bg-gradient-to-br from-gray-700 to-gray-900 rounded-full flex items-center justify-center text-white text-sm font-medium shrink-0">
                      {comment.username[0].toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-900">@{comment.username}</span>
                        <span className="text-xs font-light text-gray-500">{formatTimeAgo(comment.timestamp)}</span>
                        {comment.replied && (
                          <span className="text-xs font-light text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Replied</span>
                        )}
                      </div>
                      <p className="text-sm font-light text-gray-700">{comment.text}</p>
                    </div>
                    {!comment.replied && (
                      <button className="px-3 py-1.5 bg-[#FFD766] text-gray-900 rounded-full text-xs font-light hover:bg-[#FFD766]/90 shrink-0">
                        Reply
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Pipeline Status */}
          <div className="col-span-6 bg-white rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-light text-gray-900">Content Pipeline</h3>
              <button
                onClick={loadData}
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-full text-sm font-light text-gray-700 transition-colors"
              >
                Refresh
              </button>
            </div>

            <div className="space-y-3 max-h-[280px] overflow-y-auto">
              {contents.slice(0, 5).length === 0 ? (
                <div className="text-center py-8 text-gray-500 font-light">
                  No content yet
                </div>
              ) : (
                contents.slice(0, 5).map((content) => (
                  <div key={content.id} className="bg-gray-50 rounded-[16px] overflow-hidden">
                    {/* Parent: Crawled Content */}
                    <div className="p-3 flex items-center gap-3">
                      <button
                        onClick={() => toggleContent(content.id)}
                        className="w-5 h-5 flex items-center justify-center hover:bg-gray-200 rounded transition-colors shrink-0"
                      >
                        <svg
                          className={`w-4 h-4 text-gray-600 transition-transform ${expandedContents.has(content.id) ? 'rotate-90' : ''}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>

                      <div className={`w-2 h-2 rounded-full shrink-0 ${
                        content.thread_status === 'published' ? 'bg-green-500' :
                        content.thread_status === 'ready' ? 'bg-[#FFD766]' :
                        'bg-gray-400'
                      }`}></div>

                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-medium text-gray-900 truncate">{content.title}</h4>
                      </div>

                      <motion.button
                        onClick={() => handleProcess(content.id)}
                        disabled={processing === content.id}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="px-3 py-1.5 bg-[#FFD766] text-gray-900 rounded-full text-xs font-light hover:bg-[#FFD766]/90 disabled:opacity-50 shrink-0"
                      >
                        {processing === content.id ? 'Generating...' : '+ New'}
                      </motion.button>
                    </div>

                    {/* Children: Generated Posts */}
                    <AnimatePresence>
                      {expandedContents.has(content.id) && generatedPosts[content.id] && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="border-t border-gray-200"
                        >
                          <div className="p-3 space-y-2">
                            {generatedPosts[content.id].length === 0 ? (
                              <div className="text-center py-4 text-xs text-gray-500 font-light">
                                No generated posts yet
                              </div>
                            ) : (
                              generatedPosts[content.id].map((post) => (
                                <div key={post.id} className="bg-white rounded-lg p-3 border border-gray-200">
                                  <div className="flex items-start gap-2 mb-2">
                                    <div className={`w-2 h-2 rounded-full shrink-0 mt-1 ${
                                      post.status === 'published' ? 'bg-green-500' :
                                      post.status === 'failed' ? 'bg-red-500' :
                                      'bg-[#FFD766]'
                                    }`}></div>
                                    <p className="text-xs font-light text-gray-700 flex-1 line-clamp-2">
                                      {post.generated_post.substring(0, 100)}...
                                    </p>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    {(post.status === 'ready' || post.status === 'failed') && (
                                      <>
                                        <button
                                          onClick={() => handleEditPost(post)}
                                          className="px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded-full text-xs font-light text-gray-700"
                                        >
                                          Edit
                                        </button>
                                        <button
                                          onClick={() => handlePublishPost(post.id, post.content_id)}
                                          disabled={processing === post.id}
                                          className="px-2 py-1 bg-[#FFD766] hover:bg-[#FFD766]/90 rounded-full text-xs font-light text-gray-900"
                                        >
                                          {processing === post.id ? 'Publishing...' : post.status === 'failed' ? 'Retry' : 'Publish'}
                                        </button>
                                      </>
                                    )}
                                    {post.status === 'published' && (
                                      <>
                                        <span className="px-2 py-1 bg-green-50 text-green-600 rounded-full text-xs font-light">
                                          Published
                                        </span>
                                        {post.threads_permalink && (
                                          <a
                                            href={post.threads_permalink}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-light hover:bg-green-200"
                                          >
                                            View on Threads
                                          </a>
                                        )}
                                      </>
                                    )}
                                    <button
                                      onClick={() => handleDeletePost(post.id, post.content_id)}
                                      className="px-2 py-1 text-red-600 hover:bg-red-50 rounded-full text-xs font-light ml-auto"
                                    >
                                      Delete
                                    </button>
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={() => window.location.href = '/content'}
              className="w-full mt-4 py-3 border border-gray-200 hover:bg-gray-50 rounded-full text-sm font-light text-gray-700 transition-colors"
            >
              View All Content
            </button>
          </div>

          {/* Top Performing Posts */}
          <div className="col-span-6 bg-white rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-light text-gray-900">Top Performing</h3>
              <select className="px-3 py-1.5 bg-gray-100 rounded-full text-sm font-light text-gray-700 border-0 focus:outline-none focus:ring-2 focus:ring-[#FFD766]">
                <option>This Week</option>
                <option>This Month</option>
                <option>All Time</option>
              </select>
            </div>

            <div className="space-y-4">
              {contents.filter(c => c.thread_status === 'published').slice(0, 3).map((content, i) => (
                <div key={content.id} className="flex items-start gap-4 p-4 bg-gray-50 rounded-[20px]">
                  <div className="w-8 h-8 bg-[#FFD766] rounded-full flex items-center justify-center text-gray-900 text-sm font-medium shrink-0">
                    #{i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-gray-900 mb-2 truncate">{content.title}</h4>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1">
                        <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        <span className="text-xs font-light text-gray-600">{Math.floor(Math.random() * 5000 + 1000)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <svg className="w-4 h-4 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                        </svg>
                        <span className="text-xs font-light text-gray-600">{Math.floor(Math.random() * 500 + 100)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                        </svg>
                        <span className="text-xs font-light text-gray-600">{Math.floor(Math.random() * 100 + 20)}</span>
                      </div>
                    </div>
                  </div>
                  <a
                    href={content.extra_data?.threads_permalink as string || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 rounded-full text-xs font-light text-gray-700 transition-colors shrink-0"
                  >
                    View
                  </a>
                </div>
              ))}

              {contents.filter(c => c.thread_status === 'published').length === 0 && (
                <div className="text-center py-8 text-gray-500 font-light">
                  No published posts yet
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="col-span-6 bg-gradient-to-br from-gray-900 to-gray-800 rounded-[32px] p-8 shadow-[0_2px_16px_rgba(0,0,0,0.08)] text-white">
            <h3 className="text-lg font-light mb-6">Quick Actions</h3>

            <div className="grid grid-cols-2 gap-4">
              <motion.button
                onClick={handleNewPost}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur rounded-[20px] text-left transition-colors"
              >
                <svg className="w-6 h-6 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                <div className="text-sm font-light">New Post</div>
                <div className="text-xs font-light text-white/60 mt-1">Create manually</div>
              </motion.button>

              <motion.button
                onClick={handleAutoReplySettings}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur rounded-[20px] text-left transition-colors"
              >
                <svg className="w-6 h-6 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <div className="text-sm font-light">Auto Reply Settings</div>
                <div className="text-xs font-light text-white/60 mt-1">Configure AI</div>
              </motion.button>

              <motion.button
                onClick={handleAnalytics}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur rounded-[20px] text-left transition-colors"
              >
                <svg className="w-6 h-6 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
                <div className="text-sm font-light">Analytics</div>
                <div className="text-xs font-light text-white/60 mt-1">View insights</div>
              </motion.button>

              <motion.button
                onClick={handleCrawlNow}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="p-4 bg-white/10 hover:bg-white/20 backdrop-blur rounded-[20px] text-left transition-colors"
              >
                <svg className="w-6 h-6 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
                <div className="text-sm font-light">Crawl Now</div>
                <div className="text-xs font-light text-white/60 mt-1">Start crawling</div>
              </motion.button>
            </div>
          </div>
        </div>
      </div>

      {/* Modal */}
      {showModal && generatedPost && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-8"
          onClick={closeModal}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className="bg-white rounded-[32px] max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b border-gray-200 px-8 py-6 rounded-t-[32px] flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-light text-gray-900">Generated Thread Post</h2>
                <p className="text-sm font-light text-gray-500 mt-1">{selectedPost ? `Post #${selectedPost.id.slice(0, 8)}` : selectedContent?.title}</p>
              </div>
              <button
                onClick={closeModal}
                className="w-10 h-10 flex items-center justify-center hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-8 space-y-6">
              {/* 편집 가능한 포스트 리스트 */}
              <div className="space-y-4">
                {editedPosts.map((post, index) => (
                  <div key={index} className="bg-gradient-to-br from-[#FFD766]/10 to-[#FFD766]/5 rounded-[24px] p-6 border border-[#FFD766]/20">
                    <div className="flex items-center gap-2 mb-4">
                      <svg className="w-5 h-5 text-[#FFD766]" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                      </svg>
                      <h3 className="text-lg font-light text-gray-900">
                        포스트 {index + 1}/{editedPosts.length}
                      </h3>
                    </div>
                    <textarea
                      value={post}
                      onChange={(e) => handlePostEdit(index, e.target.value)}
                      className="w-full min-h-[200px] p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#FFD766] focus:border-transparent font-light text-gray-800 leading-relaxed resize-y"
                      placeholder="포스트 내용을 입력하세요..."
                    />
                  </div>
                ))}
              </div>

              <div className="bg-gray-50 rounded-[24px] p-6">
                <div className="flex items-center gap-2 mb-4">
                  <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <h3 className="text-lg font-light text-gray-900">AI Analysis</h3>
                </div>
                <p className="text-sm font-light text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {generatedPost.analysis}
                </p>
              </div>

              {generatedPost.webSearch && (
                <div className="bg-blue-50 rounded-[24px] p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <h3 className="text-lg font-light text-gray-900">Fact Check Results</h3>
                  </div>
                  <p className="text-sm font-light text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {generatedPost.webSearch}
                  </p>
                </div>
              )}

              <div className="flex gap-4 pt-4">
                {isEdited ? (
                  <motion.button
                    onClick={selectedPost ? handleSavePost : handleSave}
                    disabled={isSaving}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 px-6 py-4 bg-green-600 text-white rounded-full font-light hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isSaving ? '저장 중...' : '저장'}
                  </motion.button>
                ) : selectedPost ? (
                  <motion.button
                    onClick={() => handlePublishPost(selectedPost.id, selectedPost.content_id)}
                    disabled={!!processing}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 px-6 py-4 bg-gray-900 text-white rounded-full font-light hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {processing ? 'Publishing to Threads...' : 'Publish to Threads'}
                  </motion.button>
                ) : (
                  <motion.button
                    onClick={() => selectedContent && handleApprove(selectedContent.id)}
                    disabled={!!processing}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 px-6 py-4 bg-gray-900 text-white rounded-full font-light hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {processing ? 'Publishing to Threads...' : 'Approve & Publish to Threads'}
                  </motion.button>
                )}
                <motion.button
                  onClick={() => setShowModal(false)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="px-6 py-4 bg-white border border-gray-300 text-gray-700 rounded-full font-light hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </motion.button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}
