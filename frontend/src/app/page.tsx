"use client"

import { ShaderAnimation } from "@/components/ui/shader-lines";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Shader Background */}
      <ShaderAnimation />
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" />

      {/* Content */}
      <div className="relative z-10">
        {/* Navigation */}
        <nav className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-white">Trend AI Studio</h1>
            <div className="flex gap-4">
              <Link
                href="/dashboard"
                className="px-6 py-2 text-white hover:text-yellow-400 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/dashboard"
                className="px-6 py-2 bg-yellow-400 text-gray-900 font-semibold rounded-lg hover:bg-yellow-500 transition-colors"
              >
                Get Started
              </Link>
            </div>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="container mx-auto px-6 pt-20 pb-32 text-center">
          <h1 className="text-6xl md:text-7xl font-bold text-white mb-6 leading-tight">
            AI-Powered Content
            <br />
            <span className="text-yellow-400">Analysis & Generation</span>
          </h1>
          <p className="text-xl md:text-2xl text-gray-300 mb-12 max-w-3xl mx-auto">
            Automatically discover trending content, analyze with AI,
            <br />
            and publish to Threads in minutes.
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/dashboard"
              className="px-8 py-4 bg-yellow-400 text-gray-900 font-bold text-lg rounded-lg hover:bg-yellow-500 transition-all transform hover:scale-105"
            >
              Start Free Trial
            </Link>
            <button className="px-8 py-4 bg-white/10 backdrop-blur text-white font-semibold text-lg rounded-lg border border-white/20 hover:bg-white/20 transition-all">
              Watch Demo
            </button>
          </div>

          {/* Stats */}
          <div className="flex gap-12 justify-center mt-20">
            <div>
              <div className="text-4xl font-bold text-yellow-400">10K+</div>
              <div className="text-gray-400 mt-1">Content Analyzed</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-yellow-400">95%</div>
              <div className="text-gray-400 mt-1">Accuracy</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-yellow-400">5min</div>
              <div className="text-gray-400 mt-1">Average Time</div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="container mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">
              Powerful Features
            </h2>
            <p className="text-xl text-gray-300">
              Everything you need to automate your content workflow
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all">
              <div className="w-12 h-12 bg-yellow-400/20 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Smart Crawling</h3>
              <p className="text-gray-400">
                Automatically discover trending content from multiple sources with intelligent filtering.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all">
              <div className="w-12 h-12 bg-yellow-400/20 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">AI Analysis</h3>
              <p className="text-gray-400">
                Powered by Gemini to analyze content, extract insights, and generate engaging posts.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all">
              <div className="w-12 h-12 bg-yellow-400/20 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Auto Publishing</h3>
              <p className="text-gray-400">
                Seamlessly publish to Threads with one click. Schedule and manage all your posts.
              </p>
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="container mx-auto px-6 py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">
              How It Works
            </h2>
            <p className="text-xl text-gray-300">
              From discovery to publishing in 3 simple steps
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="text-center">
              <div className="w-16 h-16 bg-yellow-400 text-gray-900 rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                1
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Discover</h3>
              <p className="text-gray-400">
                Our crawler finds trending content from your selected sources
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-yellow-400 text-gray-900 rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                2
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Analyze</h3>
              <p className="text-gray-400">
                AI analyzes and generates optimized posts for your audience
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-yellow-400 text-gray-900 rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                3
              </div>
              <h3 className="text-xl font-bold text-white mb-2">Publish</h3>
              <p className="text-gray-400">
                Review and publish to Threads with a single click
              </p>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="container mx-auto px-6 py-20">
          <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 rounded-3xl p-12 text-center">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Ready to Get Started?
            </h2>
            <p className="text-xl text-gray-800 mb-8">
              Join teams already using Trend AI Studio to automate their content workflow
            </p>
            <Link
              href="/dashboard"
              className="inline-block px-8 py-4 bg-gray-900 text-white font-bold text-lg rounded-lg hover:bg-gray-800 transition-all transform hover:scale-105"
            >
              Start Free Trial
            </Link>
          </div>
        </section>

        {/* Footer */}
        <footer className="container mx-auto px-6 py-12 border-t border-white/10">
          <div className="text-center text-gray-400">
            <p>© 2026 Trend AI Studio. All rights reserved.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
