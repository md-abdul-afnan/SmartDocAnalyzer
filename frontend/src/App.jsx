import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import jsPDF from "jspdf";

function getApiBaseUrl() {
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (fromEnv !== undefined && String(fromEnv).trim() !== "") {
    return String(fromEnv).replace(/\/$/, "");
  }
  if (import.meta.env.DEV) {
    return "http://127.0.0.1:8000/api";
  }
  return "/api";
}

const API_BASE_URL = getApiBaseUrl();
const HISTORY_STORAGE_KEY = "smart-document-analyzer-history";
const MAX_HISTORY_ITEMS = 50;
const TRANSLATION_TARGETS = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "ar", label: "Arabic" },
  { code: "ta", label: "Tamil" },
  { code: "te", label: "Telugu" },
  { code: "ur", label: "Urdu" },
];

const OCR_TO_TRANSLATION_LANG = {
  eng: "en",
  hin: "hi",
  spa: "es",
  fra: "fr",
  ara: "ar",
  tam: "ta",
  tel: "te",
  urd: "ur",
};

function formatApiDetail(detail) {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item != null && "msg" in item
          ? String(item.msg)
          : JSON.stringify(item)
      )
      .filter(Boolean)
      .join("; ");
  }
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String(detail.message);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return "Request failed.";
  }
}

function readHistoryFromStorage() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeHistoryToStorage(items) {
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items));
}

function LoadingDots() {
  const dots = [0, 1, 2];

  return (
    <div className="flex items-center gap-2" aria-label="loading">
      {dots.map((dot) => (
        <motion.span
          // Repeating vertical bounce for loading feedback.
          key={dot}
          className="h-3 w-3 rounded-full bg-indigo-600"
          animate={{ y: [0, -8, 0] }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: dot * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
      <span className="ml-2 text-sm text-slate-600">Analyzing document...</span>
    </div>
  );
}

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [language, setLanguage] = useState("eng");
  const [availableLanguages, setAvailableLanguages] = useState(["eng"]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [translateTarget, setTranslateTarget] = useState("en");
  const [translatedResult, setTranslatedResult] = useState(null);
  const [translating, setTranslating] = useState(false);
  const [history, setHistory] = useState(() => readHistoryFromStorage());
  const [currentHistoryId, setCurrentHistoryId] = useState(null);
  const [backendNotice, setBackendNotice] = useState("");

  useEffect(() => {
    const loadLanguages = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/languages`);
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.languages) || data.languages.length === 0) {
          setBackendNotice(
            "Could not load OCR languages from the server. Check that the API is running and CORS allows this site."
          );
          return;
        }
        setBackendNotice("");
        setAvailableLanguages(data.languages);
        if (!data.languages.includes(language)) {
          setLanguage(data.languages.includes("eng") ? "eng" : data.languages[0]);
        }
      } catch {
        setBackendNotice(
          `Cannot reach the API at ${API_BASE_URL}. On Render, open the API service once to wake it (free tier cold start can take ~1 minute), then refresh this page.`
        );
      }
    };

    loadLanguages();
  }, []);

  const addHistoryEntry = (entry) => {
    setHistory((prev) => {
      const next = [entry, ...prev.filter((item) => item.id !== entry.id)].slice(
        0,
        MAX_HISTORY_ITEMS
      );
      writeHistoryToStorage(next);
      return next;
    });
  };

  const updateHistoryTranslation = (historyId, translation) => {
    if (!historyId) return;
    setHistory((prev) => {
      const next = prev.map((item) =>
        item.id === historyId ? { ...item, translatedResult: translation } : item
      );
      writeHistoryToStorage(next);
      return next;
    });
  };

  const removeHistoryEntry = (historyId) => {
    setHistory((prev) => {
      const next = prev.filter((item) => item.id !== historyId);
      writeHistoryToStorage(next);
      return next;
    });
    if (currentHistoryId === historyId) {
      setCurrentHistoryId(null);
    }
  };

  const clearAllHistory = () => {
    writeHistoryToStorage([]);
    setHistory([]);
    setCurrentHistoryId(null);
  };

  const openHistoryEntry = (item) => {
    setError("");
    setResult(item.result);
    setTranslatedResult(item.translatedResult || null);
    setCurrentHistoryId(item.id);
    setSelectedFile(null);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError("Please choose a PDF, image, or text file first.");
      return;
    }

    setError("");
    setLoading(true);
    setResult(null);
    setTranslatedResult(null);
    setCurrentHistoryId(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_BASE_URL}/upload?language=${language}`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }
      setResult(data);
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const entry = {
        id,
        createdAt: new Date().toISOString(),
        sourceName: selectedFile.name,
        result: data,
        translatedResult: null,
      };
      addHistoryEntry(entry);
      setCurrentHistoryId(id);
    } catch (err) {
      setError(err.message || "Something went wrong while analyzing.");
    } finally {
      setLoading(false);
    }
  };

  const isTextDocument = selectedFile
    ? selectedFile.type === "text/plain" ||
      /\.(txt|md)$/i.test(selectedFile.name || "")
    : false;

  const handleDownloadPdf = () => {
    if (!result) return;
    const doc = new jsPDF();
    const lines = doc.splitTextToSize(
      `Summary:\n${result.summary}\n\nKey Points:\n${(result.key_points || [])
        .map((point) => `- ${point}`)
        .join("\n")}`,
      180
    );
    doc.setFontSize(12);
    doc.text(lines, 10, 15);
    doc.save("document-summary.pdf");
  };

  const handleTranslate = async () => {
    if (!result?.extracted_text?.trim()) {
      setError("No extracted text available to translate.");
      return;
    }

    setError("");
    setTranslating(true);
    setTranslatedResult(null);

    try {
      const sourceLanguage = OCR_TO_TRANSLATION_LANG[language] || "auto";
      const textsToTranslate = [
        { key: "extracted_text", text: result.extracted_text || "" },
        { key: "summary", text: result.summary || "" },
        { key: "key_points", text: (result.key_points || []).join("\n") },
      ];

      const translatedEntries = await Promise.all(
        textsToTranslate.map(async (item) => {
          if (!item.text.trim()) {
            return { key: item.key, translated: "" };
          }
          const response = await fetch(`${API_BASE_URL}/translate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text: item.text,
              source_language: sourceLanguage,
              target_language: translateTarget,
            }),
          });
          let data = {};
          try {
            data = await response.json();
          } catch {
            throw new Error(`Translation failed (HTTP ${response.status}).`);
          }
          if (!response.ok) {
            const msg = formatApiDetail(data.detail) || "Translation failed.";
            throw new Error(msg);
          }
          return { key: item.key, translated: data.translated_text || "" };
        })
      );

      const translatedMap = Object.fromEntries(
        translatedEntries.map((entry) => [entry.key, entry.translated])
      );
      const translatedKeyPoints = (translatedMap.key_points || "")
        .split("\n")
        .map((point) => point.trim())
        .filter(Boolean);

      const nextTranslated = {
        extracted_text: translatedMap.extracted_text || "",
        summary: translatedMap.summary || "",
        key_points: translatedKeyPoints,
      };
      setTranslatedResult(nextTranslated);
      updateHistoryTranslation(currentHistoryId, nextTranslated);
    } catch (err) {
      setError(err.message || "Something went wrong while translating.");
    } finally {
      setTranslating(false);
    }
  };

  return (
    <motion.main
      // Page-load fade with slight upward motion for polished entry.
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="min-h-screen bg-gradient-to-br from-slate-100 to-indigo-100 px-4 py-10"
    >
      <div className="mx-auto max-w-4xl rounded-2xl bg-white p-6 shadow-xl md:p-8">
        <h1 className="text-3xl font-bold text-slate-800">Smart Document Analyzer</h1>
        <p className="mt-2 text-slate-600">
          Upload PDFs, images, or plain text files (.txt, .md) to extract text and get AI insights.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Without an OpenAI key, summaries use either a local Hugging Face model (when enabled) or
          a fast extractive summary, and translation uses free online services. Add OPENAI_API_KEY on
          the server for stronger summaries, image description, and optional vision OCR.
        </p>
        {backendNotice ? (
          <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            {backendNotice}
          </p>
        ) : null}

        <motion.label
          // Hover scale effect on upload box.
          whileHover={{ scale: 1.02 }}
          transition={{ type: "spring", stiffness: 260, damping: 20 }}
          className="mt-6 block cursor-pointer rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50 p-6 text-center"
        >
          <span className="block text-sm font-medium text-indigo-700">
            Click to upload PDF / JPG / PNG / TXT / MD
          </span>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.txt,.md,text/plain"
            className="mt-3 w-full text-sm text-slate-700"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
          />
          {selectedFile && (
            <p className="mt-2 text-xs text-slate-500">Selected: {selectedFile.name}</p>
          )}
        </motion.label>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            {isTextDocument ? (
              <p className="text-sm text-slate-600">
                Plain text files use your file contents directly (OCR is not used).
              </p>
            ) : (
              <>
                <label className="mr-2 text-sm font-medium text-slate-700">OCR Language:</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                >
                  {availableLanguages.map((code) => (
                    <option key={code} value={code}>
                      {code.toUpperCase()} ({code})
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>

          <motion.button
            // Tap animation gives click feedback.
            whileTap={{ scale: 0.95 }}
            whileHover={{ scale: 1.02 }}
            transition={{ type: "spring", stiffness: 320, damping: 18 }}
            onClick={handleAnalyze}
            disabled={loading}
            className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:bg-indigo-400"
          >
            Analyze Document
          </motion.button>
        </div>

        {error && <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <div className="mt-5">{loading && <LoadingDots />}</div>

        {history.length > 0 && (
          <section className="mt-8 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-semibold text-slate-800">History</h2>
              <button
                type="button"
                onClick={clearAllHistory}
                className="text-sm font-medium text-red-600 hover:text-red-700"
              >
                Clear all
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Stored in this browser only. Open a past analysis to view it again.
            </p>
            <ul className="mt-3 max-h-52 space-y-2 overflow-y-auto text-sm">
              {history.map((item) => (
                <li
                  key={item.id}
                  className="flex flex-col gap-2 rounded-lg bg-white p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-800" title={item.sourceName}>
                      {item.sourceName}
                    </p>
                    <p className="text-xs text-slate-500">
                      {new Date(item.createdAt).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => openHistoryEntry(item)}
                      className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      onClick={() => removeHistoryEntry(item.id)}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <AnimatePresence mode="wait">
          {result && (
            <motion.section
              key="result"
              // Gravity-like drop and settle effect with spring.
              initial={{ opacity: 0, y: -25 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              transition={{ type: "spring", stiffness: 120, damping: 14 }}
              className="mt-7 space-y-5 rounded-xl bg-slate-50 p-5"
            >
              <motion.div
                // Extracted text slides in from left.
                initial={{ opacity: 0, x: -40 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.55, ease: "easeOut" }}
              >
                <h2 className="text-lg font-semibold text-slate-800">Extracted Text</h2>
                <p className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap rounded bg-white p-3 text-sm text-slate-700">
                  {result.extracted_text}
                </p>
              </motion.div>

              <motion.div
                // Summary appears with simple fade.
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.15, duration: 0.5 }}
              >
                <h2 className="text-lg font-semibold text-slate-800">Summary</h2>
                <p className="mt-2 rounded bg-white p-3 text-sm text-slate-700">{result.summary}</p>
              </motion.div>

              <motion.div
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: {},
                  visible: { transition: { staggerChildren: 0.12, delayChildren: 0.2 } },
                }}
              >
                <h2 className="text-lg font-semibold text-slate-800">Key Points</h2>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-slate-700">
                  {(result.key_points || []).map((point, idx) => (
                    <motion.li
                      // Staggered bullet reveal.
                      key={`${point}-${idx}`}
                      variants={{
                        hidden: { opacity: 0, y: 8 },
                        visible: { opacity: 1, y: 0 },
                      }}
                      transition={{ duration: 0.35, ease: "easeOut" }}
                    >
                      {point}
                    </motion.li>
                  ))}
                </ul>
              </motion.div>

              <motion.button
                whileTap={{ scale: 0.97 }}
                whileHover={{ scale: 1.01 }}
                onClick={handleDownloadPdf}
                className="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white"
              >
                Download Summary as PDF
              </motion.button>

              <div className="rounded-lg bg-white p-4">
                <h2 className="text-lg font-semibold text-slate-800">
                  Translate Extracted Text, Summary, and Key Points
                </h2>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
                  <select
                    value={translateTarget}
                    onChange={(e) => setTranslateTarget(e.target.value)}
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm"
                  >
                    {TRANSLATION_TARGETS.map((item) => (
                      <option key={item.code} value={item.code}>
                        {item.label} ({item.code})
                      </option>
                    ))}
                  </select>
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    whileHover={{ scale: 1.01 }}
                    onClick={handleTranslate}
                    disabled={translating}
                    className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-emerald-400"
                  >
                    {translating ? "Translating..." : "Translate"}
                  </motion.button>
                </div>

                {translatedResult && (
                  <div className="mt-3 space-y-3">
                    <div className="rounded bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-600">Translated Extracted Text</p>
                      <p className="mt-1 max-h-52 overflow-auto whitespace-pre-wrap text-sm text-slate-700">
                        {translatedResult.extracted_text}
                      </p>
                    </div>
                    <div className="rounded bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-600">Translated Summary</p>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
                        {translatedResult.summary}
                      </p>
                    </div>
                    <div className="rounded bg-slate-50 p-3">
                      <p className="text-xs font-semibold text-slate-600">Translated Key Points</p>
                      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {(translatedResult.key_points || []).map((point, idx) => (
                          <li key={`${point}-${idx}`}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              {result.image_description && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2, duration: 0.45 }}
                >
                  <h2 className="text-lg font-semibold text-slate-800">Image Description</h2>
                  <p className="mt-2 rounded bg-white p-3 text-sm text-slate-700">
                    {result.image_description}
                  </p>
                </motion.div>
              )}
            </motion.section>
          )}
        </AnimatePresence>
      </div>
    </motion.main>
  );
}

export default App;
