// EduQuest Pro - Super Network & WebSocket Interceptor v1.3.12 (Runs in page context)
(function () {
  console.log("[EduQuest Interceptor v1.3.12] Active in page context (Fetch + XHR + WebSocket)");

  function getShortUrl() {
    try {
      const host = window.location.hostname.replace(/^www\./, "");
      const path = window.location.pathname;
      if (!path || path === "/") return host;
      const cleanPath = path.replace(/\/$/, "");
      return host + (cleanPath.length > 20 ? cleanPath.substring(0, 18) + "…" : cleanPath);
    } catch (e) {
      return "online";
    }
  }

  function sendInterceptorLog(msg, type = "info", detail = null) {
    try {
      window.postMessage({
        source: "EDUQUEST_INTERCEPTOR",
        type: "INTERCEPTOR_LOG",
        log: {
          msg: msg,
          type: type, // 'info' | 'success' | 'warn' | 'error' | 'net' | 'skip'
          source: getShortUrl(),
          detail: detail,
          time: new Date().toLocaleTimeString()
        }
      }, "*");
    } catch (e) {}
  }

  sendInterceptorLog(`⚡ Interceptor v1.3.11 đã kích hoạt trên ${window.location.hostname}`, "info");

  function isUuidOrIdString(str) {
    if (!str || typeof str !== "string") return false;
    const trimmed = str.trim();
    // UUID pattern (e.g. b718a2a2-ba6f-4119-bf1c-f2eae36df160)
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed)) return true;
    // Hex string without spaces
    if (/^[0-9a-f]{16,64}$/i.test(trimmed)) return true;
    // Single word token without whitespace and longer than 20 chars
    if (!/\s/.test(trimmed) && trimmed.length > 20) return true;
    // Pure numeric ID
    if (/^\d+$/.test(trimmed)) return true;
    return false;
  }

  function isNewsOrPromoText(str) {
    if (!str || typeof str !== "string") return false;
    const lower = str.toLowerCase();
    const badKeywords = [
      "hướng dẫn học sinh tham gia", "hướng dẫn tham gia", "bài thi thử khám phá", "thi thử khám phá",
      "thông báo mở bài thi", "thông báo mở", "thông báo v/v", "thông báo số", "thông báo kết quả", "thông báo tổ chức",
      "rộn ràng đón", "trăng rằm", "tựu trường", "bứt phá", "khám phá combo", "combo đồng hành",
      "khóa học combo", "ưu đãi", "khuyến mại", "thể lệ giải đấu", "cơ cấu giải thưởng",
      "danh sách nhận thưởng", "chúc mừng các thí sinh", "lễ vinh danh", "lễ trao giải",
      "tin tức & sự kiện", "tin nổi bật", "bài viết mới nhất", "hướng dẫn phụ huynh",
      "điều khoản sử dụng", "chính sách bảo mật", "quy định thi", "thể lệ cuộc thi", "vnmf",
      "chúc mừng, bạn vừa chiến thắng", "kết quả trận đấu", "bảng xếp hạng trận đấu"
    ];
    return badKeywords.some(kw => lower.includes(kw));
  }

  function getQuestionContent(obj) {
    if (!obj || typeof obj !== "object") return "";
    let c = "";
    if (typeof obj.content === "string") c = obj.content;
    else if (typeof obj.question_content === "string") c = obj.question_content;
    else if (typeof obj.question_text === "string") c = obj.question_text;
    else if (typeof obj.question_body === "string") c = obj.question_body;
    else if (typeof obj.question_html === "string") c = obj.question_html;
    else if (typeof obj.body === "string") c = obj.body;
    else if (typeof obj.stem === "string") c = obj.stem;
    else if (typeof obj.text === "string") c = obj.text;
    else if (typeof obj.question === "string" && !isUuidOrIdString(obj.question)) c = obj.question;
    else if (obj.question && typeof obj.question === "object") {
      c = getQuestionContent(obj.question);
    }
    return c ? c.trim() : "";
  }

  function getQuestionOptions(obj) {
    if (!obj || typeof obj !== "object") return [];
    let opts = obj.answers || obj.options || obj.list_answer || obj.list_answers ||
               obj.choices || obj.items || obj.sub_questions || obj.suggests || obj.selects ||
               obj.options_list || obj.list_suggests || obj.user_answers;
    
    // Support VioEdu textDropdownAnswers
    if ((!opts || opts.length === 0) && Array.isArray(obj.textDropdownAnswers) && obj.textDropdownAnswers.length > 0) {
      const ddList = [];
      obj.textDropdownAnswers.forEach(item => {
        if (item && Array.isArray(item.list)) {
          item.list.forEach(o => {
            if (o && (o.text || o.content)) ddList.push({ content: o.text || o.content, text: o.text || o.content });
          });
        }
      });
      if (ddList.length > 0) return ddList;
    }

    // Support VioEdu Matching (leftMatching & rightMatching)
    if ((!opts || opts.length === 0) && Array.isArray(obj.leftMatching) && Array.isArray(obj.rightMatching)) {
      const matchList = [];
      obj.leftMatching.forEach((lm, idx) => {
        const rm = obj.rightMatching[idx] || {};
        const lText = lm.textContent || lm.text || lm.content || "";
        const rText = rm.textContent || rm.text || rm.content || "";
        if (lText || rText) matchList.push({ content: `${lText} ↔ ${rText}` });
      });
      if (matchList.length > 0) return matchList;
    }

    if (!opts && obj.question && typeof obj.question === "object") {
      opts = getQuestionOptions(obj.question);
    }
    return Array.isArray(opts) ? opts : [];
  }

  function normalizeCapturedItem(obj) {
    if (!obj || typeof obj !== "object") return obj;
    const content = getQuestionContent(obj);
    const answers = getQuestionOptions(obj);
    const id = obj.id || obj._id || obj.question_id || (obj.question && (obj.question.id || obj.question._id)) || null;
    const rightAns = obj.right_answer || obj.correct_answer || (obj.question && (obj.question.right_answer || obj.question.correct_answer)) || null;
    const explanation = obj.explanation || obj.solution || obj.guide || (obj.question && (obj.question.explanation || obj.question.solution)) || "";

    return {
      ...(obj.question && typeof obj.question === "object" ? obj.question : {}),
      ...obj,
      id: id,
      content: content,
      answers: answers,
      right_answer: rightAns,
      explanation: explanation
    };
  }

  function isQuestionObject(obj) {
    if (!obj || typeof obj !== "object") return false;

    // 1. Skip CMS articles, blog posts, news banners
    if (obj.slug || obj.post_type || obj.category_id || obj.news_id || obj.banner_url) {
      return false;
    }

    // 2. Extract content and reject UUIDs or news titles
    const content = getQuestionContent(obj);
    if (!content) return false;

    if (isUuidOrIdString(content)) {
      sendInterceptorLog(`[MẠNG BỎ QUA] Từ chối UUID '${content.substring(0, 16)}...' (không phải đề bài)`, "skip");
      return false;
    }

    if (isNewsOrPromoText(content)) {
      sendInterceptorLog(`[MẠNG BỎ QUA] Từ chối bài viết tin tức/quảng cáo: '${content.substring(0, 32)}...'`, "skip");
      return false;
    }

    if (content.length < 8) return false;

    const rawOptions = getQuestionOptions(obj);
    const hasOptions = Array.isArray(rawOptions) && rawOptions.length >= 2;
    const isDedicatedQuestion = Boolean(
      obj.questionType !== undefined || obj.question_type !== undefined ||
      obj.skillName || obj.depthOfKnowledge || obj.skillDemo ||
      obj.correct_answer || obj.right_answer || obj.solution || obj.explanation ||
      (obj.question && typeof obj.question === "object")
    );

    // Check educational signals (math, pedagogical keywords)
    const hasMathSignal = /[\$\\\+\*\/=><%]|\\frac|\\sqrt|\b(?:tính|phép tính|biểu thức|phân số|chu vi|diện tích|hình vuông|hình tròn|hình tam giác|đoạn thẳng|số|chó|mèo|quả|rổ|thuyền|người|bao nhiêu|mấy)\b/i.test(content) || content.includes("math-tex");
    const hasPromptSignal = /\?|câu\s*\d+|bài\s*\d+|\bbài tập khám phá\b|\bkhám phá\s*:|vận dụng|hãy chọn|chọn đáp án|\btính\b|\btìm\b|\bđiền\b|\bcho\b|\bhỏi\b|sau đây|biết rằng|hình vẽ|khoanh|đặt tính|ghép|nối|đúng ghi|sai ghi|trong hình/i.test(content);

    if (hasOptions) {
      sendInterceptorLog(`[MẠNG BẮT ĐƯỢC] Phát hiện câu hỏi (${rawOptions.length} đáp án): '${content.substring(0, 35)}...'`, "success");
      return true;
    }
    if (isDedicatedQuestion) {
      sendInterceptorLog(`[MẠNG BẮT ĐƯỢC] Phát hiện câu hỏi chuyên biệt VioEdu/LMS: '${content.substring(0, 35)}...'`, "success");
      return true;
    }
    if (hasMathSignal || hasPromptSignal) {
      sendInterceptorLog(`[MẠNG BẮT ĐƯỢC] Phát hiện bài tập giáo dục: '${content.substring(0, 35)}...'`, "success");
      return true;
    }

    return false;
  }

  const IGNORED_KEYS = new Set([
    "user", "auth", "ranking", "leaderboard", "avatar", "profile",
    "news", "posts", "post", "articles", "article", "banners", "banner",
    "notifications", "notification", "categories", "category", "menus", "menu",
    "configs", "config", "sliders", "slider", "footers", "headers", "blogs", "blog",
    "events", "event", "announcements", "announcement", "products", "product", "promotions", "promotion",
    "combos", "combo", "courses", "course", "packages", "package", "transactions", "orders", "payments"
  ]);

  function extractQuestionsDeep(data, maxDepth = 5) {
    const results = [];
    if (!data || maxDepth <= 0) return results;

    if (Array.isArray(data)) {
      for (const item of data) {
        if (isQuestionObject(item)) {
          results.push(normalizeCapturedItem(item));
        } else if (typeof item === "object" && item !== null) {
          results.push(...extractQuestionsDeep(item, maxDepth - 1));
        }
      }
    } else if (typeof data === "object" && data !== null) {
      if (isQuestionObject(data)) {
        results.push(normalizeCapturedItem(data));
      }
      for (const key of Object.keys(data)) {
        if (IGNORED_KEYS.has(key.toLowerCase())) continue;
        const val = data[key];
        if (typeof val === "object" && val !== null) {
          results.push(...extractQuestionsDeep(val, maxDepth - 1));
        }
      }
    }
    return results;
  }

  function notifyCaptured(questions, urlSource) {
    if (!questions || questions.length === 0) return;
    try {
      sendInterceptorLog(`🎯 Bóc tách thành công ${questions.length} câu hỏi từ ${urlSource}`, "success");
      window.postMessage({
        source: "EDUQUEST_INTERCEPTOR",
        type: "NETWORK_QUESTION_CAPTURED",
        url: urlSource,
        payload: questions
      }, "*");
    } catch (e) {
      console.error("[EduQuest Interceptor] PostMessage error:", e);
    }
  }

  const isEduDomain = window.location.hostname.includes("vio.edu.vn") || 
                      window.location.hostname.includes("tnmath.edu.vn") || 
                      window.location.hostname.includes("trangnguyen.edu.vn") ||
                      window.location.hostname.includes("hanhtrangso.nxbgd.vn") ||
                      window.location.hostname.includes("vietjack.com") ||
                      window.location.hostname.includes("loigiaihay.com") ||
                      window.location.hostname.includes("vndoc.com") ||
                      window.location.hostname.includes("hoc247.net") ||
                      window.location.hostname.includes("ioe.vn");

  function cleanHtmlToText(html) {
    if (!html) return "";
    return html.replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();
  }

  function parseVioEduGraphQLItem(item) {
    if (!item || !item.content) return null;
    let options = [];
    if (Array.isArray(item.answers) && item.answers.length > 0) {
      options = item.answers.map((a, i) => ({
        id: String.fromCharCode(65 + i),
        content: cleanHtmlToText(a.text || a.content || "")
      }));
    } else if (Array.isArray(item.textDropdownAnswers) && item.textDropdownAnswers.length > 0) {
      const list = item.textDropdownAnswers[0]?.list || [];
      options = list.map((dd, i) => ({
        id: String.fromCharCode(65 + i),
        content: dd.text || dd.content || ""
      }));
    } else if (Array.isArray(item.leftMatching) && Array.isArray(item.rightMatching)) {
      options = item.leftMatching.map((lm, i) => ({
        id: String(i + 1),
        content: (lm.textContent || lm.text || "") + " ↔ " + (item.rightMatching[i]?.textContent || item.rightMatching[i]?.text || "")
      }));
    }

    return {
      id: "vioedu_gql_" + (item._id || item.id || Date.now()),
      source_platform: "vioedu",
      grade: item.grade || 1,
      topic: item.skillName || "VioEdu Luyện tập & Đấu trường",
      question_type: options.length > 0 ? "single_choice" : "fill_blank",
      content_html: item.content,
      content_text: cleanHtmlToText(item.content),
      options: options,
      correct_answer: null,
      difficulty: item.depthOfKnowledge || "medium"
    };
  }

  // Also scan common client-side page state variables
  function scanWindowVariables() {
    try {
      const candidates = [
        window.__NEXT_DATA__, window.__NUXT__, window.PAGE_DATA,
        window.quizData, window.lessonData, window.exerciseData,
        window.questionsData, window.testData,
        window.App?.apolloState, window.__APOLLO_STATE__
      ];
      for (const cand of candidates) {
        if (cand && typeof cand === "object") {
          const qs = extractQuestionsDeep(cand);
          if (qs.length > 0) {
            sendInterceptorLog(`🔍 Tìm thấy ${qs.length} câu hỏi trong biến đối tượng window`, "success");
            notifyCaptured(qs, "Window State Object");
          }
        }
      }
    } catch (e) {}
  }
  setTimeout(scanWindowVariables, 1500);
  setTimeout(scanWindowVariables, 4500);

  // 1. Hook window.fetch
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);
    try {
      const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || "";
      const shouldInspect = isEduDomain || 
                            url.includes("graphql") || url.includes("api") || url.includes("arena") || url.includes("battle") ||
                            url.includes("quiz") || url.includes("question") || url.includes("contest") ||
                            url.includes("round") || url.includes("play") || url.includes("skill") ||
                            url.includes("exam") || url.includes("practice") || url.includes("lesson") ||
                            url.includes("bai-hoc") || url.includes("luyen-tap") || url.includes("exercise") ||
                            url.includes("sach-dien-tu") || url.includes("activity") || url.includes("onboard");

      if (shouldInspect) {
        const cloned = response.clone();
        cloned.json().then(data => {
          sendInterceptorLog(`[Fetch] Nhận phản hồi từ: ${url.substring(0, 65)}...`, "net");

          // Handle VioEdu GraphQL Practice Question
          const gqlQuestion = data?.data?.getPracticeQuestionBySkillId || data?.getPracticeQuestionBySkillId;
          if (gqlQuestion) {
            const parsed = parseVioEduGraphQLItem(gqlQuestion);
            if (parsed) {
              notifyCaptured([parsed], "VioEdu GraphQL API");
              return;
            }
          }

          // Handle VioEdu GraphQL Result / Solution
          const gqlResult = data?.data?.getQuestionResultQuery || data?.getQuestionResultQuery;
          if (gqlResult) {
            const explains = gqlResult.explainPractice || gqlResult.explain || [];
            if (Array.isArray(explains) && explains.length > 0) {
              const expText = explains.map(e => e.text || e.content || "").join("\n");
              window.postMessage({
                source: "EDUQUEST_INTERCEPTOR",
                type: "QUESTION_SOLUTION_CAPTURED",
                explanation: expText,
                userAnswered: gqlResult.userAnswered
              }, "*");
            }
          }

          const questions = extractQuestionsDeep(data);
          if (questions.length > 0) {
            notifyCaptured(questions, "Fetch: " + (url || "API"));
          }
        }).catch(() => {});
      }
    } catch (err) {}
    return response;
  };

  // 2. Hook XMLHttpRequest (Supports both responseType='' / 'text' and Angular's responseType='json')
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._eduquest_url = url;
    this._eduquest_method = method;
    return originalOpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("load", function () {
      try {
        const url = this._eduquest_url || "";
        const method = this._eduquest_method || "GET";
        let data = null;

        // CRITICAL FIX: In browsers, accessing this.responseText throws InvalidStateError when responseType === "json"!
        if (this.responseType === "json" && this.response) {
          data = this.response;
        } else if (this.responseType === "" || this.responseType === "text") {
          const text = this.responseText;
          if (text && (text.trim().startsWith("{") || text.trim().startsWith("["))) {
            data = JSON.parse(text);
          }
        } else if (this.response && typeof this.response === "object") {
          data = this.response;
        }

        if (data) {
          sendInterceptorLog(`[XHR ${method}] Bắt gói tin từ: ${url.substring(0, 65)}... (type: ${this.responseType || 'text'})`, "net");
          const questions = extractQuestionsDeep(data);
          if (questions.length > 0) {
            notifyCaptured(questions, "XHR: " + (url || "XHR"));
          }
        }
      } catch (e) {
        console.error("[EduQuest Interceptor] XHR process error:", e);
      }
    });
    return originalSend.apply(this, args);
  };

  // 3. Hook window.WebSocket (for Live Realtime Arena / Battle Matches)
  if (typeof window.WebSocket !== "undefined") {
    const OriginalWebSocket = window.WebSocket;
    window.WebSocket = function (...args) {
      const ws = new OriginalWebSocket(...args);
      const wsUrl = args[0] || "WebSocket";

      sendInterceptorLog(`[WebSocket] Kết nối realtime tới: ${wsUrl.substring(0, 60)}...`, "net");

      ws.addEventListener("message", function (event) {
        try {
          if (typeof event.data === "string") {
            let raw = event.data;
            // Handle Socket.IO packets (e.g. 42["event_name", payload] or 43[...])
            if (/^\d{2}/.test(raw)) {
              raw = raw.replace(/^\d+/, "");
            }
            if (raw.startsWith("[") || raw.startsWith("{")) {
              const data = JSON.parse(raw);
              const questions = extractQuestionsDeep(data);
              if (questions.length > 0) {
                notifyCaptured(questions, "WebSocket: " + wsUrl);
              }
            }
          }
        } catch (e) {}
      });

      return ws;
    };
    window.WebSocket.prototype = OriginalWebSocket.prototype;
  }
})();
