// 100% Pure ECMAScript 5 (ES5) for iOS 6.1.3 Mobile Safari
// Optimized for iPhone 4s (512MB RAM, Low Memory Footprint)

(function() {
  // DOM Elements Cache
  var dom = {};

  function initDomCache() {
    dom.clockTime = document.getElementById("clock-time");
    dom.clockDate = document.getElementById("clock-date");

    dom.weatherTemp = document.getElementById("weather-temp");
    dom.weatherDesc = document.getElementById("weather-desc");
    dom.weatherApp = document.getElementById("weather-apparent");
    dom.weatherHum = document.getElementById("weather-humidity");
    dom.weatherCity = document.getElementById("weather-city");

    dom.stockList = document.getElementById("stock-list");
    dom.stockTime = document.getElementById("stock-update-time");

    dom.audio = document.getElementById("audio-player");
    dom.musicTitle = document.getElementById("music-title");
    dom.playBtn = document.getElementById("btn-play");
    dom.prevBtn = document.getElementById("btn-prev");
    dom.nextBtn = document.getElementById("btn-next");
    dom.btnShuffle = document.getElementById("btn-shuffle");
    dom.btnLoop = document.getElementById("btn-loop");
    dom.progBar = document.getElementById("progress-bar");
    dom.progContainer = document.getElementById("progress-container");
    dom.currTimeElem = document.getElementById("current-time");
    dom.durTimeElem = document.getElementById("duration-time");
    dom.trackCount = document.getElementById("music-track-count");

    dom.msgList = document.getElementById("message-list");
    dom.msgForm = document.getElementById("msg-form");
    dom.msgAuthor = document.getElementById("msg-author");
    dom.msgContent = document.getElementById("msg-content");
    dom.sendBtn = document.getElementById("btn-send");

    dom.themeName = document.getElementById("current-theme-name");
    dom.themeGrid = document.getElementById("theme-grid");
    dom.themeModal = document.getElementById("theme-modal");

    dom.radioPlayer = document.getElementById("radio-player");
    dom.radioDot = document.getElementById("radio-dot");
    dom.radioTitle = document.getElementById("radio-title");
    dom.radioStatus = document.getElementById("radio-status");
    dom.radioGrid = document.getElementById("radio-grid");
    dom.btnRadioPlay = document.getElementById("btn-radio-play");
    dom.btnRadioStop = document.getElementById("btn-radio-stop");

    dom.guideTopic = document.getElementById("guidance-topic");
    dom.guideQuote = document.getElementById("guidance-quote");
    dom.guideDesc = document.getElementById("guidance-desc");
    dom.guideCounter = document.getElementById("guidance-counter");
    dom.btnGuideListen = document.getElementById("btn-guide-listen");
    dom.btnGuideRepeat = document.getElementById("btn-guide-repeat");
    dom.btnGuideNext = document.getElementById("btn-guide-next");
    dom.guidePlayer = document.getElementById("guidance-player");

    dom.wisdomCard = document.getElementById("wisdom-deck-box");
    dom.wisdomCategory = document.getElementById("wisdom-category");
    dom.wisdomQuote = document.getElementById("wisdom-quote");
    dom.wisdomDetail = document.getElementById("wisdom-detail");
    dom.wisdomCounter = document.getElementById("wisdom-card-counter");
    dom.btnWisdomNext = document.getElementById("btn-wisdom-next");
    dom.btnWisdomRandom = document.getElementById("btn-wisdom-random");
  }

  // Memory-Safe Helper: AJAX GET (nulls out xhr to break closure leaks)
  function ajaxGet(url, onSuccess, onError) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, true);
    xhr.onreadystatechange = function() {
      if (xhr && xhr.readyState === 4) {
        var status = xhr.status;
        var text = xhr.responseText;
        xhr.onreadystatechange = null;
        xhr = null;
        if (status >= 200 && status < 300) {
          try {
            var data = JSON.parse(text);
            if (onSuccess) onSuccess(data);
          } catch(e) {
            if (onError) onError(e);
          }
        } else {
          if (onError) onError(status);
        }
      }
    };
    xhr.send(null);
  }

  // Memory-Safe Helper: AJAX POST (JSON)
  function ajaxPost(url, payload, onSuccess, onError) {
    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    xhr.onreadystatechange = function() {
      if (xhr && xhr.readyState === 4) {
        var status = xhr.status;
        var text = xhr.responseText;
        xhr.onreadystatechange = null;
        xhr = null;
        if (status >= 200 && status < 300) {
          try {
            var data = JSON.parse(text);
            if (onSuccess) onSuccess(data);
          } catch(e) {
            if (onError) onError(e);
          }
        } else {
          if (onError) onError(status);
        }
      }
    };
    xhr.send(JSON.stringify(payload));
  }

  // 1. Digital Clock Module
  var weekDays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  var lastDateStr = "";

  function updateClock() {
    var now = new Date();
    var h = now.getHours();
    var m = now.getMinutes();
    var s = now.getSeconds();

    var hStr = (h < 10 ? "0" : "") + h;
    var mStr = (m < 10 ? "0" : "") + m;
    var sStr = (s < 10 ? "0" : "") + s;

    if (dom.clockTime) {
      dom.clockTime.innerHTML = hStr + ":" + mStr + ":" + sStr;
    }

    var day = now.getDate();
    if (day !== lastDateStr) {
      lastDateStr = day;
      var year = now.getFullYear();
      var month = now.getMonth() + 1;
      var wDay = weekDays[now.getDay()];
      if (dom.clockDate) {
        dom.clockDate.innerHTML = year + "年" + month + "月" + day + "日 " + wDay;
      }
    }
  }

  // 2. Weather Module
  function fetchWeather() {
    ajaxGet("/api/weather", function(data) {
      if (dom.weatherTemp) dom.weatherTemp.innerHTML = data.temperature;
      if (dom.weatherDesc) dom.weatherDesc.innerHTML = data.description;
      if (dom.weatherApp) dom.weatherApp.innerHTML = data.apparent;
      if (dom.weatherHum) dom.weatherHum.innerHTML = data.humidity;
      if (dom.weatherCity && data.city) dom.weatherCity.innerHTML = data.city.split(" ")[0];
    }, function(err) {});
  }

  // 3. Stock Module (大盤即時點數與漲跌)
  var isUsStocksExpanded = false;
  var lastStockStr = "";

  window.toggleUsStocks = function() {
    isUsStocksExpanded = !isUsStocksExpanded;
    var wrapper = document.getElementById("us-stocks-wrapper");
    var hint = document.getElementById("stock-toggle-hint");
    if (wrapper) {
      wrapper.style.display = isUsStocksExpanded ? "block" : "none";
    }
    if (hint) {
      hint.innerHTML = isUsStocksExpanded ? "點擊收合美股 &#9650;" : "點擊展開美股 &#9660;";
    }
  };

  function fetchStocks() {
    ajaxGet("/api/stocks", function(data) {
      if (!dom.stockList) return;

      var items = data.items || [];
      if (items.length === 0) return;

      var currentSnapshot = JSON.stringify(items);
      // Skip DOM rebuild if data hasn't changed
      if (currentSnapshot === lastStockStr && dom.stockList.children.length > 0) {
        if (dom.stockTime && data.updated_at) {
          dom.stockTime.innerHTML = data.updated_at + " 更新";
        }
        return;
      }
      lastStockStr = currentSnapshot;

      if (dom.stockTime && data.updated_at) {
        dom.stockTime.innerHTML = data.updated_at + " 更新";
      }

      var twStock = items[0];
      var twUpClass = twStock.is_up ? "stock-up" : "stock-down";
      var twArrow = twStock.is_up ? "&#9650; " : "&#9660; ";
      var hintText = isUsStocksExpanded ? "點擊收合美股 &#9650;" : "點擊展開美股 &#9660;";

      var html = "";
      // 主大盤（台股加權指數），點擊可展開/收合美股
      html += '<div class="stock-item primary-stock" onclick="window.toggleUsStocks();">';
      html += '  <div class="stock-name">';
      html += '    <strong>' + twStock.name + '</strong>';
      html += '    <span id="stock-toggle-hint" class="stock-toggle-hint">' + hintText + '</span>';
      html += '  </div>';
      html += '  <div class="stock-digits">';
      html += '    <span class="stock-price">' + twStock.price + '</span>';
      html += '    <span class="stock-change ' + twUpClass + '">' + twArrow + twStock.change + ' (' + twStock.change_pct + ')</span>';
      html += '  </div>';
      html += '</div>';

      // 美股收合區塊
      var displayStyle = isUsStocksExpanded ? "block" : "none";
      html += '<div id="us-stocks-wrapper" class="us-stocks-wrapper" style="display: ' + displayStyle + ';">';
      html += '  <div class="us-stocks-header">國際美股大盤行情</div>';

      for (var i = 1; i < items.length; i++) {
        var it = items[i];
        var upClass = it.is_up ? "stock-up" : "stock-down";
        var arrow = it.is_up ? "&#9650; " : "&#9660; ";

        html += '<div class="stock-item">';
        html += '  <div class="stock-name">' + it.name + '</div>';
        html += '  <div class="stock-digits">';
        html += '    <span class="stock-price">' + it.price + '</span>';
        html += '    <span class="stock-change ' + upClass + '">' + arrow + it.change + ' (' + it.change_pct + ')</span>';
        html += '  </div>';
        html += '</div>';
      }
      html += '</div>';

      dom.stockList.innerHTML = html;
    }, function(err) {});
  }

  // 4. Music Player Module
  var playlist = [];
  var currentIndex = 0;
  var isPlaying = false;
  var isShuffle = false;
  var loopMode = 0; // 0: 全部循環, 1: 單曲循環, 2: 關閉循環
  var lastUpdateSec = -1;

  function formatTime(secs) {
    if (isNaN(secs)) return "00:00";
    var m = Math.floor(secs / 60);
    var s = Math.floor(secs % 60);
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }

  function loadTrack(idx) {
    if (!playlist || playlist.length === 0) return;
    if (idx < 0) idx = playlist.length - 1;
    if (idx >= playlist.length) idx = 0;
    currentIndex = idx;

    var track = playlist[currentIndex];
    if (dom.audio) {
      dom.audio.src = track.url;
    }
    if (dom.musicTitle) {
      dom.musicTitle.innerHTML = (currentIndex + 1) + ". " + track.title;
    }
    lastUpdateSec = -1;
  }

  function playTrack() {
    if (playlist.length === 0 || !dom.audio) return;
    stopRadio();
    stopGuidance();
    if (!dom.audio.src) {
      loadTrack(0);
    }
    dom.audio.play();
    isPlaying = true;
    if (dom.playBtn) dom.playBtn.innerHTML = "&#10074;&#10074; 暫停";
  }

  function pauseTrack() {
    if (!dom.audio) return;
    dom.audio.pause();
    isPlaying = false;
    if (dom.playBtn) dom.playBtn.innerHTML = "&#9654; 播放";
  }

  function getNextIndex(isForward) {
    if (playlist.length <= 1) return 0;
    if (isShuffle) {
      var nextIdx = Math.floor(Math.random() * playlist.length);
      if (nextIdx === currentIndex && playlist.length > 1) {
        nextIdx = (currentIndex + 1) % playlist.length;
      }
      return nextIdx;
    }
    if (isForward) {
      if (currentIndex + 1 >= playlist.length) {
        return (loopMode === 2) ? -1 : 0;
      }
      return currentIndex + 1;
    } else {
      if (currentIndex - 1 < 0) {
        return playlist.length - 1;
      }
      return currentIndex - 1;
    }
  }

  function handleTrackEnd() {
    if (loopMode === 1) {
      if (dom.audio) {
        dom.audio.currentTime = 0;
        dom.audio.play();
      }
    } else {
      var nextIdx = getNextIndex(true);
      if (nextIdx === -1) {
        pauseTrack();
        if (dom.audio) dom.audio.currentTime = 0;
      } else {
        loadTrack(nextIdx);
        playTrack();
      }
    }
  }

  function setupMusicPlayer() {
    if (dom.btnShuffle) {
      dom.btnShuffle.onclick = function() {
        isShuffle = !isShuffle;
        dom.btnShuffle.className = isShuffle ? "retro-sub-btn active" : "retro-sub-btn";
        dom.btnShuffle.innerHTML = isShuffle ? "&#128256; 隨機: 開" : "&#128256; 隨機: 關";
      };
    }

    if (dom.btnLoop) {
      dom.btnLoop.onclick = function() {
        loopMode = (loopMode + 1) % 3;
        if (loopMode === 0) {
          dom.btnLoop.className = "retro-sub-btn";
          dom.btnLoop.innerHTML = "&#128257; 循環: 全部";
        } else if (loopMode === 1) {
          dom.btnLoop.className = "retro-sub-btn active";
          dom.btnLoop.innerHTML = "&#128258; 單曲循環";
        } else {
          dom.btnLoop.className = "retro-sub-btn";
          dom.btnLoop.innerHTML = "&#10145; 循環: 關閉";
        }
      };
    }

    if (dom.playBtn) {
      dom.playBtn.onclick = function() {
        if (isPlaying) {
          pauseTrack();
        } else {
          playTrack();
        }
      };
    }

    if (dom.prevBtn) {
      dom.prevBtn.onclick = function() {
        var prevIdx = getNextIndex(false);
        loadTrack(prevIdx);
        playTrack();
      };
    }

    if (dom.nextBtn) {
      dom.nextBtn.onclick = function() {
        var nextIdx = getNextIndex(true);
        if (nextIdx === -1) nextIdx = 0;
        loadTrack(nextIdx);
        playTrack();
      };
    }

    if (dom.audio) {
      // Throttled timeupdate: only update DOM when second actually changes
      dom.audio.addEventListener("timeupdate", function() {
        if (!dom.audio.duration) return;
        var curSec = Math.floor(dom.audio.currentTime);
        if (curSec !== lastUpdateSec) {
          lastUpdateSec = curSec;
          var pct = (curSec / dom.audio.duration) * 100;
          if (dom.progBar) dom.progBar.style.width = pct + "%";
          if (dom.currTimeElem) dom.currTimeElem.innerHTML = formatTime(curSec);
          if (dom.durTimeElem) dom.durTimeElem.innerHTML = formatTime(dom.audio.duration);
        }
      }, false);

      dom.audio.addEventListener("ended", function() {
        handleTrackEnd();
      }, false);
    }

    if (dom.progContainer) {
      dom.progContainer.onclick = function(e) {
        if (!dom.audio || !dom.audio.duration) return;
        var rect = dom.progContainer.getBoundingClientRect();
        var clickX = e.clientX - rect.left;
        var width = rect.width;
        var targetTime = (clickX / width) * dom.audio.duration;
        dom.audio.currentTime = targetTime;
      };
    }

    // Load music playlist
    ajaxGet("/api/music/list", function(tracks) {
      playlist = tracks || [];
      if (dom.trackCount) {
        dom.trackCount.innerHTML = playlist.length + " 首曲目";
      }
      if (playlist.length > 0) {
        loadTrack(0);
      } else {
        if (dom.musicTitle) dom.musicTitle.innerHTML = "music/ 資料夾尚無音訊";
      }
    });
  }

  // 5. Message Board Module
  var lastMessagesStr = "";

  function renderMessages(messages) {
    if (!dom.msgList) return;
    if (!messages || messages.length === 0) {
      dom.msgList.innerHTML = '<div class="msg-loading">目前尚無留言</div>';
      return;
    }

    var snapshot = JSON.stringify(messages);
    if (snapshot === lastMessagesStr && dom.msgList.children.length > 0) {
      return; // Skip DOM re-render if messages have not changed
    }
    lastMessagesStr = snapshot;

    var html = "";
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i];
      html += '<div class="msg-item">';
      html += '  <div class="msg-header-row">';
      html += '    <span class="msg-author-name">' + m.author + '</span>';
      html += '    <span class="msg-time-tag">' + m.time + '</span>';
      html += '  </div>';
      html += '  <div class="msg-text-content">' + m.content + '</div>';
      html += '</div>';
    }
    dom.msgList.innerHTML = html;
  }

  function fetchMessages() {
    ajaxGet("/api/messages", function(data) {
      renderMessages(data);
    });
  }

  function setupMessageForm() {
    if (dom.msgForm) {
      dom.msgForm.onsubmit = function() {
        var author = dom.msgAuthor ? dom.msgAuthor.value : "";
        var content = dom.msgContent ? dom.msgContent.value : "";
        if (!content || content.replace(/^\s+|\s+$/g, "") === "") {
          alert("請輸入留言內容！");
          return false;
        }

        if (dom.sendBtn) dom.sendBtn.disabled = true;

        ajaxPost("/api/messages", {
          author: author,
          content: content
        }, function(res) {
          if (dom.sendBtn) dom.sendBtn.disabled = false;
          if (dom.msgContent) dom.msgContent.value = "";
          lastMessagesStr = ""; // Force re-render
          fetchMessages();
        }, function(err) {
          if (dom.sendBtn) dom.sendBtn.disabled = false;
          alert("留言送出失敗，請稍後再試。");
        });

        return false;
      };
    }
  }

  // 6. Theme Switcher Module (10 Distinct Mood Themes)
  var THEMES = [
    { id: "skeuomorphic", name: "經典擬物", color: "#38bdf8" },
    { id: "cyberpunk",    name: "賽博龐克", color: "#ff007f" },
    { id: "luxury-gold",  name: "黑金奢華", color: "#ffd700" },
    { id: "vaporwave",    name: "80s 卡帶", color: "#ff71ce" },
    { id: "emerald",      name: "極光翡翠", color: "#34d399" },
    { id: "zen-wood",     name: "和風原木", color: "#c4a482" },
    { id: "scifi-shuttle",name: "太空穿梭機", color: "#f97316" },
    { id: "rose-gold",    name: "法式玫瑰金", color: "#f43f5e" },
    { id: "gameboy",      name: "Game Boy", color: "#9bbc0f" },
    { id: "matrix",       name: "終端黑客", color: "#00ff66" }
  ];

  var currentThemeIndex = 0;

  function renderThemeGrid() {
    if (!dom.themeGrid) return;
    var html = "";
    for (var i = 0; i < THEMES.length; i++) {
      var t = THEMES[i];
      var isActive = (i === currentThemeIndex);
      html += '<button type="button" class="theme-option-item ' + (isActive ? 'active' : '') + '" onclick="window.switchDashboardTheme(\'' + t.id + '\');">';
      html += '  <span class="theme-preview-color" style="background-color: ' + t.color + ';"></span>';
      html += '  <span>' + (i + 1) + '. ' + t.name + '</span>';
      if (isActive) {
        html += '  <span style="float: right; color: #38bdf8; font-weight: bold;">&#10004;</span>';
      }
      html += '</button>';
    }
    dom.themeGrid.innerHTML = html;
  }

  function applyTheme(themeId) {
    var found = false;
    for (var i = 0; i < THEMES.length; i++) {
      if (THEMES[i].id === themeId) {
        currentThemeIndex = i;
        found = true;
        break;
      }
    }
    if (!found) {
      currentThemeIndex = 0;
      themeId = THEMES[0].id;
    }

    // Remove existing theme classes from body
    var currentClass = document.body.className || "";
    var classes = currentClass.split(/\s+/);
    var newClasses = [];
    for (var j = 0; j < classes.length; j++) {
      if (classes[j].indexOf("theme-") !== 0) {
        newClasses.push(classes[j]);
      }
    }
    newClasses.push("theme-" + themeId);
    document.body.className = newClasses.join(" ");

    // Update theme name in top-bar
    if (dom.themeName) {
      dom.themeName.innerHTML = THEMES[currentThemeIndex].name;
    }

    // Save to localStorage
    try {
      localStorage.setItem("retro_dashboard_theme", themeId);
    } catch(e) {}

    // Update active in modal if open
    renderThemeGrid();
  }

  function nextTheme() {
    var nextIdx = (currentThemeIndex + 1) % THEMES.length;
    applyTheme(THEMES[nextIdx].id);
  }

  function openThemeModal() {
    if (dom.themeModal) {
      renderThemeGrid();
      dom.themeModal.style.display = "block";
    }
  }

  function closeThemeModal() {
    if (dom.themeModal) {
      dom.themeModal.style.display = "none";
    }
  }

  function setupThemeSwitcher() {
    window.switchDashboardTheme = function(themeId) {
      applyTheme(themeId);
      closeThemeModal();
    };

    var btnPicker = document.getElementById("btn-theme-picker");
    var btnNext = document.getElementById("btn-theme-next");
    var btnClose = document.getElementById("btn-close-theme");
    var backdrop = document.getElementById("theme-modal-backdrop");

    if (btnPicker) {
      btnPicker.onclick = function() {
        openThemeModal();
      };
    }
    if (btnNext) {
      btnNext.onclick = function() {
        nextTheme();
      };
    }
    if (btnClose) {
      btnClose.onclick = function() {
        closeThemeModal();
      };
    }
    if (backdrop) {
      backdrop.onclick = function() {
        closeThemeModal();
      };
    }

    // Restore saved theme
    var savedTheme = null;
    try {
      savedTheme = localStorage.getItem("retro_dashboard_theme");
    } catch(e) {}
    applyTheme(savedTheme || "skeuomorphic");
  }

  // 7. Live Radio & Lofi Streaming Module (騷操作 3)
  var RADIO_STATIONS = [
    { id: "icrt", name: "ICRT FM 100.7", genre: "西洋流行 / 英語電台", url: "https://stream.rcs.revma.com/nkdfurztxp3vv" },
    { id: "asia", name: "亞洲電台 92.7", genre: "熱門華語流行音樂", url: "https://stream.rcs.revma.com/xpgtqc74hv8uv" },
    { id: "lofi", name: "24/7 Lofi Chillhop", genre: "工作讀書 / 深夜放鬆", url: "https://streams.ilovemusic.de/iloveradio17.mp3" },
    { id: "fly",  name: "飛揚調頻 89.5", genre: "懷舊金曲 / 時代老歌", url: "https://stream.rcs.revma.com/e0tdah74hv8uv" },
    { id: "dance",name: "舞曲活力 Hits", genre: "歐美動感電音派對", url: "https://streams.ilovemusic.de/iloveradio2.mp3" },
    { id: "asia-pac", name: "亞太電台 92.3", genre: "流行生活音樂網", url: "https://stream.rcs.revma.com/kydend74hv8uv" }
  ];

  var currentRadioIndex = 0;
  var isRadioPlaying = false;

  function selectRadioStation(idx) {
    if (idx < 0 || idx >= RADIO_STATIONS.length) return;
    currentRadioIndex = idx;
    var st = RADIO_STATIONS[idx];

    if (dom.radioTitle) dom.radioTitle.innerHTML = st.name;
    if (dom.radioStatus) dom.radioStatus.innerHTML = st.genre + " &bull; 點擊收聽";

    renderRadioGrid();

    if (isRadioPlaying) {
      playRadio();
    }
  }

  function playRadio() {
    if (!dom.radioPlayer) return;
    // 互斥：暫停本機 MP3 播放器與開示語音
    pauseTrack();
    stopGuidance();

    var st = RADIO_STATIONS[currentRadioIndex];
    if (dom.radioPlayer.src !== st.url) {
      dom.radioPlayer.src = st.url;
    }

    if (dom.radioStatus) dom.radioStatus.innerHTML = "連線中... 正在載入即時電台";
    dom.radioPlayer.play();
    isRadioPlaying = true;

    if (dom.btnRadioPlay) dom.btnRadioPlay.innerHTML = "&#10074;&#10074; 暫停廣播";
    if (dom.radioDot) dom.radioDot.className = "radio-live-dot active";
  }

  function stopRadio() {
    if (!dom.radioPlayer) return;
    dom.radioPlayer.pause();
    dom.radioPlayer.src = "";
    isRadioPlaying = false;

    if (dom.btnRadioPlay) dom.btnRadioPlay.innerHTML = "&#9654; 收聽電台";
    if (dom.radioDot) dom.radioDot.className = "radio-live-dot";
    if (dom.radioStatus) dom.radioStatus.innerHTML = "已停止播放 &bull; 點擊頻道收聽";
  }

  function toggleRadio() {
    if (isRadioPlaying) {
      dom.radioPlayer.pause();
      isRadioPlaying = false;
      if (dom.btnRadioPlay) dom.btnRadioPlay.innerHTML = "&#9654; 繼續收聽";
      if (dom.radioDot) dom.radioDot.className = "radio-live-dot";
      if (dom.radioStatus) dom.radioStatus.innerHTML = "已暫停 &bull; 點擊繼續";
    } else {
      playRadio();
    }
  }

  function renderRadioGrid() {
    if (!dom.radioGrid) return;
    var html = "";
    for (var i = 0; i < RADIO_STATIONS.length; i++) {
      var s = RADIO_STATIONS[i];
      var isActive = (i === currentRadioIndex);
      html += '<button type="button" class="radio-station-btn ' + (isActive ? 'active' : '') + '" onclick="window.switchRadioStation(' + i + ');">';
      html += '  <span class="radio-station-name">' + s.name + '</span>';
      html += '  <span class="radio-station-genre">' + s.genre + '</span>';
      html += '</button>';
    }
    dom.radioGrid.innerHTML = html;
  }

  function setupRadioPlayer() {
    window.switchRadioStation = function(idx) {
      selectRadioStation(idx);
      playRadio();
    };

    if (dom.btnRadioPlay) {
      dom.btnRadioPlay.onclick = function() {
        toggleRadio();
      };
    }

    if (dom.btnRadioStop) {
      dom.btnRadioStop.onclick = function() {
        stopRadio();
      };
    }

    if (dom.radioPlayer) {
      dom.radioPlayer.addEventListener("playing", function() {
        if (dom.radioDot) dom.radioDot.className = "radio-live-dot active";
        if (dom.radioStatus) {
          var st = RADIO_STATIONS[currentRadioIndex];
          dom.radioStatus.innerHTML = "&#9679; LIVE 現場直播中 (" + st.genre + ")";
        }
      }, false);

      dom.radioPlayer.addEventListener("error", function() {
        if (dom.radioStatus) dom.radioStatus.innerHTML = "電台連線忙碌中，請點選其他頻道";
        if (dom.radioDot) dom.radioDot.className = "radio-live-dot";
      }, false);
    }

    renderRadioGrid();
    selectRadioStation(0);
  }

  // 8. Daily Master Guidance Module (師父提點祐維 每日心靈指引)
  var MASTER_GUIDANCES = [
    {
        "id": 1,
        "title": "真理與煩惱",
        "quote": "活在相裡，就會產生煩惱；活在真理，你會一直感恩。",
        "desc": "把大家對我的行為全部定義成「為我好」。「為我好」就是真理，可以帶著這個濾鏡學習更多事情。遇到煩惱，換個角度去想如何做好，但「為我好」的宗旨要留下。"
    },
    {
        "id": 2,
        "title": "沉住氣的智慧",
        "quote": "急了之後，哪怕有案子也會困難重重，要沉住氣。",
        "desc": "自己亂做容易失衡賠錢。要沉得住氣，不要慌，一步一步穩穩來。一人公司的發展，朝 SOHO 與服務業方向踏實前進。"
    },
    {
        "id": 3,
        "title": "回天的標準在於合群",
        "quote": "想回天，要合群。如果天上仙佛不合群，天上也會大亂。",
        "desc": "師父是在關心祐維，要多關心人際關係與身邊人的想法，不要把自己封閉在一個人的世界。"
    },
    {
        "id": 4,
        "title": "氣色與衣裝",
        "quote": "人要衣裝整齊，氣色要好，才不會活在自己的世界。",
        "desc": "氣色也是衣裝其中一環。把自己打理乾淨、精神清朗，走入人群，好的人緣與氣場自然會跟著來。"
    },
    {
        "id": 5,
        "title": "給自己留點緩衝",
        "quote": "不要給自己太多壓力。有緩衝、喘口氣，頭腦才能轉動。",
        "desc": "你很棒，不用給自己那麼大的壓力。先把心態放平靜，心平氣和了，應變能力和智慧自然會提升。"
    },
    {
        "id": 6,
        "title": "面對人事的不圓滿",
        "quote": "人事都會有一個缺，世間沒有真正的絕對圓滿。",
        "desc": "天時、地利、人和，佔兩個就有機會成功。不要因為有一點缺憾就氣餒，鼓勵和做得好的事情要記錄下來，然後持續做下去。"
    },
    {
        "id": 7,
        "title": "純真與付出要有認知",
        "quote": "祐維是付出型人格，純真很珍貴，但能力夠、認知要跟上。",
        "desc": "喜歡幫助人是善念，但要虧得漂亮、付出得有智慧。明白事情的優先順序，不要因為別人一句提醒就動搖了自己的初衷。"
    },
    {
        "id": 8,
        "title": "說話真誠白話",
        "quote": "大方向不要講太多複雜詞語與成語，用最真誠的心說白話。",
        "desc": "溝通時先尊重對方的意願，可以先問：「我傳達給你，你會想聽嗎？」講話真誠白話，人家聽得懂，心就能相通。"
    },
    {
        "id": 9,
        "title": "持之以恆與真心",
        "quote": "修道與助人，貴在真誠與持續行動，做表面的沒有用。",
        "desc": "不要敷衍，帶人要拿出真心。把做對的事、獲得鼓勵的事記錄下來，不被一時情緒牽動，持續不懈地走下去。"
    },
    {
        "id": 10,
        "title": "放下小時候的執念",
        "quote": "要把小時候的自己放下；當你成功以後，才能驗證小時候的自己。",
        "desc": "我自己也要給自己力量。不要鑽牛角尖，聽師父的就會了。吃飯就去吃飯，不要想那麼多。"
    },
    {
        "id": 11,
        "title": "識神放空，元神顯發",
        "quote": "識神放空，讓內在的元神顯發出來去渡人。",
        "desc": "遇到複雜煩惱，先把腦袋裡雜亂的念頭放空。心安靜了，內在本有的純淨智慧自然會顯發，引領你走對的路。"
    },
    {
        "id": 12,
        "title": "心態與投資之道",
        "quote": "投資失敗大多是心態問題：盲目自信、不認錯、凹單。",
        "desc": "股票與做事業，最忌急躁與貪念。不可凹單，一定要設好停損。心態平靜了，看清週期，財富自然會安穩隨之而來。"
    },
    {
        "id": 13,
        "title": "信念要足",
        "quote": "心如髮絲，容易被外境影響，所以信念要足。",
        "desc": "在結緣東西時，通常情況下要講「好」，代表我要的意思。堅定內在信念，不輕易動搖。"
    },
    {
        "id": 14,
        "title": "創業與渡人並進",
        "quote": "會渡人，創業也會成功；創業跟渡人要並進。",
        "desc": "遇到問題，要積極提出疑問請教師父。一次要抓兩個甚至三個重點，不要只抓一個導致其他事情失衡。"
    },
    {
        "id": 15,
        "title": "追隨師父的智慧",
        "quote": "我們是追隨師父的智慧；追隨師父，眾仙佛就會來幫忙。",
        "desc": "「智」是天上的事情，知日；「慧」和心、想法不要複雜有關。心純淨了，仙佛相助，道路自明。"
    },
    {
        "id": 16,
        "title": "放大光明，真誠用心",
        "quote": "放大光明，才有辦法成功。有心，就會持之以恆。",
        "desc": "無極、天公老祖門下弟子，要特別注意身心言行。身為弟子要主動關心，不用覺得師父很忙，師父隨時都在關心弟子。"
    },
    {
        "id": 17,
        "title": "主動回報讓師父安心",
        "quote": "不管有緣人的回應是什麼，包含考慮看看，都要主動回報師父，讓師父安心。",
        "desc": "做事情有始有終，主動回報進展，就是尊師重道與負責任的態度。"
    },
    {
        "id": 18,
        "title": "不要講人家的錯誤",
        "quote": "不該講的話不能講，不要去講人家的錯誤。",
        "desc": "修行人不會把方式改成自己舒服的方式。想法負面要隨時調整，多看他人的優點，包容他人的短處。"
    },
    {
        "id": 19,
        "title": "善意與同理心",
        "quote": "祐維是非常善良的人，情緒反應比較快，可以多找讓自己快樂的事。",
        "desc": "遇到看不過去的事，不要讓情緒長時間排斥。多點同理心，多做讓自己開心的事，把善良化為溫暖身邊人的力量。"
    },
    {
        "id": 20,
        "title": "也要神，也要人",
        "quote": "推拿配合請仙佛幫忙，雙管齊下；也要神，也要人。",
        "desc": "做事業以健康為本，盡心盡力發揮專業，同時祈請仙佛加持。人事盡到了，天助自然成。"
    },
    {
        "id": 21,
        "title": "超越虛實，做好自己",
        "quote": "不要管虛實，把自己做好。天上的功果、人間的福報，都跟自己有關。",
        "desc": "對人不要敷衍，人家有事情請我幫忙要盡心盡力。帶人拿出真心，那個關心本身就是最大的價值。"
    },
    {
        "id": 22,
        "title": "聽話照做的精神",
        "quote": "重點是有沒有聽話照做的精神；收穫多少，護持多少。",
        "desc": "師父的價值就在「因為是師父講的」。理解功果與陰德，平常運用六心，頻率相投的就多常互動。"
    },
    {
        "id": 23,
        "title": "功果自知",
        "quote": "功果做到一個程度，自然就會知道自己能否回天。",
        "desc": "不用急於一時的驗證。神來一筆是下個階段的事，腳踏實地累積陰德與功果，心安理得，前路自清。"
    },
    {
        "id": 24,
        "title": "不要鑽牛角尖",
        "quote": "我自己也要給自己力量，我要配合地球人的大腦，不要鑽牛角尖。",
        "desc": "聽師父的話就會了。生活單純化，吃飯就專心吃飯，不要想那麼久，給自己輕鬆轉身的心情。"
    },
    {
        "id": 25,
        "title": "情緒不能大於仙佛",
        "quote": "情緒大於仙佛的時候很可惜，因為不是每次都有機會。",
        "desc": "當心被情緒綁架時，往往錯失了仙佛的指引與機緣。隨時深呼吸，讓情緒降溫，智慧升起。"
    },
    {
        "id": 26,
        "title": "天時緊急，修行在身",
        "quote": "天時緊急了，要趕緊去做；最主要的是修行修道與助人渡人。",
        "desc": "照顧好自己，做好防護。修正自己完之後，自然會有方法幫助有緣人，因為自己已經親自走過這條路。"
    },
    {
        "id": 27,
        "title": "守口慎言",
        "quote": "師父給的消息不要隨便跟別人說，避免引起他人的比較心與吃醋。",
        "desc": "言語要知分寸。不該說的話不說，保護他人的人心，也守護自己的清靜。"
    },
    {
        "id": 28,
        "title": "尊師重道的一生提醒",
        "quote": "一生勸說祐維，要尊師重道，不讓融哥、師父擔憂。",
        "desc": "重視長輩與同修的話語，不合群會影響組員。把人心與私念放下，走在正道上，讓師長安心。"
    },
    {
        "id": 29,
        "title": "換位思考解煩惱",
        "quote": "遇到不想做的事，換個角度問：我要怎樣才會想做？怎樣才能讓對方不反感？",
        "desc": "不要困在對立與排斥中。轉化思考方向，找到雙方都舒服合適的方式，事情自然迎刃而解。"
    },
    {
        "id": 30,
        "title": "智慧與收入同步提升",
        "quote": "提升智慧、應變能力，心態平靜了，收入與福報自然隨之提升。",
        "desc": "多跟善知識與同修互動，學習方法。心放寬，不用給自己那麼多壓力，你本來就很棒，穩穩往前走。"
    }
];

  var currentGuideIndex = (new Date().getDate() - 1) % MASTER_GUIDANCES.length;
  var isGuidePlaying = false;
  var isGuideRepeat = false;

  function renderGuidance(idx) {
    if (idx < 0) idx = MASTER_GUIDANCES.length - 1;
    if (idx >= MASTER_GUIDANCES.length) idx = 0;
    currentGuideIndex = idx;
    var g = MASTER_GUIDANCES[currentGuideIndex];

    if (dom.guideTopic) dom.guideTopic.innerHTML = (currentGuideIndex + 1) + ". " + g.title;
    if (dom.guideQuote) dom.guideQuote.innerHTML = g.quote;
    if (dom.guideDesc) dom.guideDesc.innerHTML = g.desc;
    if (dom.guideCounter) dom.guideCounter.innerHTML = (currentGuideIndex + 1) + " / " + MASTER_GUIDANCES.length;

    if (isGuidePlaying) {
      playGuidance();
    }
  }

  function playGuidance() {
    if (!dom.guidePlayer) return;
    pauseTrack();
    stopRadio();

    var g = MASTER_GUIDANCES[currentGuideIndex];
    var audioUrl = "/static/guidance/guide_" + g.id + ".mp3";
    if (dom.guidePlayer.src.indexOf(audioUrl) === -1) {
      dom.guidePlayer.src = audioUrl;
    }

    dom.guidePlayer.play();
    isGuidePlaying = true;
    if (dom.btnGuideListen) {
      dom.btnGuideListen.className = "retro-btn btn-guide-play playing";
      dom.btnGuideListen.innerHTML = "&#10074;&#10074; 暫停聆聽";
    }
  }

  function stopGuidance() {
    if (!dom.guidePlayer) return;
    dom.guidePlayer.pause();
    isGuidePlaying = false;
    if (dom.btnGuideListen) {
      dom.btnGuideListen.className = "retro-btn btn-guide-play";
      dom.btnGuideListen.innerHTML = "&#128266; 慢慢聆聽";
    }
  }

  function toggleGuidance() {
    if (isGuidePlaying) {
      stopGuidance();
    } else {
      playGuidance();
    }
  }

  function nextGuidance() {
    var nextIdx = (currentGuideIndex + 1) % MASTER_GUIDANCES.length;
    renderGuidance(nextIdx);
  }

  function setupGuidanceModule() {
    if (dom.btnGuideListen) {
      dom.btnGuideListen.onclick = function() {
        toggleGuidance();
      };
    }

    if (dom.btnGuideRepeat) {
      dom.btnGuideRepeat.onclick = function() {
        isGuideRepeat = !isGuideRepeat;
        if (isGuideRepeat) {
          dom.btnGuideRepeat.className = "retro-sub-btn active";
          dom.btnGuideRepeat.innerHTML = "&#128258; 循環: 開";
        } else {
          dom.btnGuideRepeat.className = "retro-sub-btn";
          dom.btnGuideRepeat.innerHTML = "&#128257; 循環: 關";
        }
      };
    }

    if (dom.btnGuideNext) {
      dom.btnGuideNext.onclick = function() {
        nextGuidance();
      };
    }

    if (dom.guidePlayer) {
      dom.guidePlayer.addEventListener("ended", function() {
        if (isGuideRepeat) {
          dom.guidePlayer.currentTime = 0;
          dom.guidePlayer.play();
        } else {
          stopGuidance();
        }
      }, false);
    }

    renderGuidance(currentGuideIndex);
  }

  // ============================================================
  // 9. Wisdom Lecture Cards Module (智慧講座・心法抽卡學習 70張珍藏版)
  // ============================================================
  var WISDOM_CARDS = [
    {
        "id": 1,
        "category": "【法門根本精神】",
        "quote": "「天公疼憨人，誠心改變；老祖惜善者，渡化一切。」",
        "detail": "憨人有兩個特質：一是願意相信看不到的因果，二是誠心願意改變、修正自己不圓滿的習氣。老祖即是無極昊天老祖（玉皇上帝這一脈最古老最原始的那一尊天公老祖）。善者，是有感恩的心並願意聽話照做的人。"
    },
    {
        "id": 2,
        "category": "【因果的真諦】",
        "quote": "「萬般帶不走，唯有業隨身。因果來自於不圓滿的習氣與不足的智慧。」",
        "detail": "某幾世因為直接或間接造成的問題，源自自身的執著、偏見或不圓滿的習氣，造成因果產生。修行真正的重點在於時時刻刻自省自覺，認清自己哪裡需要調整，把過去欠缺的智慧補齊。"
    },
    {
        "id": 3,
        "category": "【宇宙觀與渺小】",
        "quote": "「仙佛掌管宇宙，地球只是一顆小星球；放下渺小的執著，心胸自然開闊。」",
        "detail": "人在浩瀚宇宙中猶如一隻微小的螞蟻，地球也只是浩瀚星海中的一顆微粒。世間所有的面子問題、一時得失，放在無窮時空裡都微不足道。放寬格局與視野，帶著謙卑生活，煩惱自消。"
    },
    {
        "id": 4,
        "category": "【合群與回天】",
        "quote": "「想回天，要合群。如果天上仙佛不合群，天上也會大亂。」",
        "detail": "多主動關心身邊人的想法與人際關係，不要把自己封閉在一個人的封閉世界。修行人在團體中修的是圓融與配合，不合群會影響組員，唯有學會合群包容，才能真正走在回天的道路上。"
    },
    {
        "id": 5,
        "category": "【尊師重道】",
        "quote": "「尊師重道，不讓融哥、師父擔憂；把人心與私念放下。」",
        "detail": "重視師長與前輩同修的話語。不合群或擅自依自己舒服的方式行事，會違逆失道。將自我的人性執念放下，聽從正道指引，讓師長安心，才是真正的同修之道。"
    },
    {
        "id": 6,
        "category": "【六心的平常運用】",
        "quote": "「平常落實運用六心，頻率相投的就多常互動，彼此提攜。」",
        "detail": "六心就是平常在生活的起心動念中時時觀照運用。理解什麼是功果、什麼是陰德，不敷衍、不造作，頻率相近的善知識多常交流，互相激勵精進。"
    },
    {
        "id": 7,
        "category": "【天時緊急】",
        "quote": "「現在是三期末法收圓的顯化，天時緊急了，要趕緊修行修道。」",
        "detail": "天時緊急，助人渡人和修行修道是當前最重要的事。先將自己的身心防護做好、習氣修正完整，自然會生出方法幫助有緣人，因為自己已經親自走過這段路。"
    },
    {
        "id": 8,
        "category": "【伯融組長開示・鑰匙與執行】",
        "quote": "「大家都拿到鑰匙（方法）了，接下來怎麼做？關鍵在於執行！」",
        "detail": "上課學習是拿到了通往智慧與突破的鑰匙，但如果不開門走進去，鑰匙只是擺設。不要只停留在聽懂的階段，把學到的邏輯立刻化為具體行動，實踐才能見真章。"
    },
    {
        "id": 9,
        "category": "【伯融組長開示・目標與習氣】",
        "quote": "「達成目標前，習氣先修正；不要在調整習氣上拖太久，因為還要渡有緣人。」",
        "detail": "如果身上的壞脾氣與不良習慣不改，再大的目標到了眼前也會被自己搞砸。檢視自己的盲點要快，調整習氣要果斷，不要拖延猶豫，因為後面還有許多等待被幫助的有緣人。"
    },
    {
        "id": 10,
        "category": "【伯融組長開示・處處為人著想】",
        "quote": "「要怎麼把對方擺第一？處處為人著想，真正看見對方的需要。」",
        "detail": "把對方擺第一不是委屈自己，而是放下自我中心的執念。在說話、做事、合作的當下，先站在對方的立場思考：他現在需要什麼？怎樣做能讓他感到舒服與被尊重？"
    },
    {
        "id": 11,
        "category": "【融哥提點・純真與認知】",
        "quote": "「純真是付出型人格的優點，但能力夠、認知要跟上，要虧得漂亮。」",
        "detail": "喜歡幫助人是珍貴的善念，但如果認知跟不上，容易被人情或金錢困住。建立正確的優先順序，付出要明明白白、有智慧，不因別人一時的提醒或評價而動搖善良的初衷。"
    },
    {
        "id": 12,
        "category": "【融哥提點・說話先問意願】",
        "quote": "「溝通時先問：『我傳達給你，你會想聽嗎？』尊重對方意願，心才能相通。」",
        "detail": "不要把自己與主管或前輩的立場綁在一起去壓對方。先確認對方的接收意願與心情狀態，讓溝通建立在平等與尊重的基礎上，對方自然容易敞開心扉。"
    },
    {
        "id": 13,
        "category": "【融哥提點・不會問靠模仿最快】",
        "quote": "「不會問、不會想、也不會說，靠模仿最快！去揣摩融哥是如何問問題的。」",
        "detail": "剛開始不會表達很正常，直接抄寫融哥或師父問問題的角度與邏輯。連動作、想法、行為都去細心觀察模仿，問久了、做過了，自然會融會貫通變成自己的能力。"
    },
    {
        "id": 14,
        "category": "【融哥提點・模仿的核心是勇敢】",
        "quote": "「想突破不會表達的障礙，核心在於自信與勇敢；敢講出自己的想法。」",
        "detail": "很多時候不敢開口是因為缺乏自信、擔心被否定。勇敢跨出第一步，即使不知道怎麼講，也可以直接問對方：『我應該如何講出來？』這就是成長的開始。"
    },
    {
        "id": 15,
        "category": "【融哥提點・來雅善圓充電】",
        "quote": "「智慧與收入想要提升，有空放假就來雅善圓，融哥會告訴你怎麼做。」",
        "detail": "自己一個人在家容易胡思亂想、鑽牛角尖。多走入道場與善知識同修身邊，在良性的互動中學習具體方法，心態放平靜了，應變能力和人生格局自然同步提升。"
    },
    {
        "id": 16,
        "category": "【融哥提點・說白話真誠心】",
        "quote": "「大方向不要講太多複雜詞語與成語，用最真誠的心說白話。」",
        "detail": "深奧的大道理不如一句溫暖真切的白話文。不用刻意包裝深澀名詞，只要發自內心為對方著想，用最樸素誠懇的話語表達，對方就能感受到你的誠意。"
    },
    {
        "id": 17,
        "category": "【融哥提點・踏實不改劇本】",
        "quote": "「依照以往的方式踏實護持，不用急著改寫劇本，重點在聽話照做。」",
        "detail": "修行和做事最忌急功近利、頻繁變換方向。守住本心，按照師長的指引一步一步扎實落實，不被外在花俏的誘惑牽引，聽話照做就是最穩健的大道。"
    },
    {
        "id": 18,
        "category": "【融哥提點・神來一筆在後頭】",
        "quote": "「神來一筆是下個階段的事，腳踏實地累積陰德與功果，心安理得。」",
        "detail": "不要一開始就追求奇蹟或神妙的靈感。先把眼前的日常功課、人際相處、本職工作做好，陰德功果積累充足了，天時地利成熟時自會水到渠成。"
    },
    {
        "id": 19,
        "category": "【轉念智慧・50%定律】",
        "quote": "「好與壞都是50%，為什麼不把預設立場換成想好的那一邊？」",
        "detail": "還沒做就先預設立場、把最慘的先想好，人就不敢往前。為什麼不去想好的那一邊？『我還沒做，但我一定做得到！』換成正面期待，生命自然朝向光明發展。"
    },
    {
        "id": 20,
        "category": "【正向思考・賺經驗值】",
        "quote": "「做不好沒關係，至少有賺到經驗值，這就是真正的正向思考。」",
        "detail": "人生不是得到就是學到。不要把一時的不順遂當成失敗，只要在過程中學到了教訓、看清了自己的不足，就是珍貴的成長資本。勇於嘗試，無怨無尤。"
    },
    {
        "id": 21,
        "category": "【習氣修煉・比較心】",
        "quote": "「比較心一定是人界的嗔恨心，讚美人家『他很棒，我要見賢思齊』。」",
        "detail": "想當仙佛嗎？仙佛會有比較心嗎？看到人家優秀，好的就虛心學習，真心讚美對方的長處，把別人的優點化為自己的養分，就不會生起人界的比較心與嫉妒。"
    },
    {
        "id": 22,
        "category": "【虛心受教・越多調整越好】",
        "quote": "「要有『越多同修前輩來調整提醒自己越好』的正向胸懷。」",
        "detail": "別人願意指出我們的盲點，是人生最大的福報與貴人。不要把提醒當作指責，心懷感激欣然接受，隨時修正自己，心性才能越磨越圓滿。"
    },
    {
        "id": 23,
        "category": "【破除思慮・遠離想太多】",
        "quote": "「想太多就和想不多的人在一起，心思單純的人不會讓你走偏。」",
        "detail": "腦袋想太多的人聚在一起，只會把問題越想越複雜、越陷越深。多去親近心思單純、腳踏實地行動的人，感染他們的純粹與幹勁，思緒自然清爽明朗。"
    },
    {
        "id": 24,
        "category": "【破除牛角尖・找貴人開導】",
        "quote": "「鑽牛角尖唯一的解法是找能開導你的貴人，學習對方的思考邏輯。」",
        "detail": "人在死胡同裡是看不見牆外的天空的。感到鑽牛角尖時，不要悶在心裡發酵，主動向有智慧的組長或師兄姐請益，借對方的雙眼看清前路。"
    },
    {
        "id": 25,
        "category": "【破除猶豫・選擇困難】",
        "quote": "「很多選項、選擇困難時，請教有判斷力的貴人給建議，依循去做。」",
        "detail": "選擇困難往往源於內心貪心或判斷力不足。與其猶豫不決浪費大好時光，不如找身邊有實戰經驗與定力的貴人指點方向，選定一條路就全力以赴。"
    },
    {
        "id": 26,
        "category": "【自律五個節奏】",
        "quote": "「自律五節奏：不拖延、思節奏、借力使力、分輕重、晨起稟報仙佛。」",
        "detail": "1. 不拖延事情馬上做。\n2. 思考下一件事的節奏（哪件先做、哪件同時做）。\n3. 尋求幫忙借力使力。\n4. 事情分輕重緩急省時間。\n5. 早上對著天空稟報，祈求仙佛讓整天圓滿順利。"
    },
    {
        "id": 27,
        "category": "【克服焦慮・求好心切】",
        "quote": "「求好心切的人要一步一步改，避免陷入沒自信與做不完的惡性循環。」",
        "detail": "想把事情一次做到完美，往往導致起步困難或中途崩潰。把大目標拆解成每天可以達成的小步驟，每完成一步就給自己一份肯定，踏實走好每一步。"
    },
    {
        "id": 28,
        "category": "【戒除隨性・不看心情】",
        "quote": "「做事不能看心情隨性好就做、不好就擺爛；把對方需求擺第一。」",
        "detail": "看心情做事是人性放縱的表現，也是貴人遠離的主因。無論當下情緒如何，答應別人的事就要負責任完成，以對方的利益與需求為優先，貴人運才會興旺。"
    },
    {
        "id": 29,
        "category": "【溝通智慧・降頻溝通】",
        "quote": "「聰明但缺乏耐性的人，溝通要降頻，給對方聽得懂的方法。」",
        "detail": "講話太快或觀念超前，對方聽不懂就會產生挫折與摩擦。學會放慢講話步調、用對方熟悉的日常比喻來交流；聽不懂時主動向有經驗的貴人請益溝通技巧。"
    },
    {
        "id": 30,
        "category": "【家庭智慧・報喜不報憂】",
        "quote": "「對家人報喜不報憂，這是一個讓家庭和諧的至深智慧。」",
        "detail": "外面的壓力與煩惱不要帶回家中傾倒給家人。家是休養生息的港灣，多分享正面積極的好消息，給家人安定的力量，立場堅定但言語要柔軟溫和。"
    },
    {
        "id": 31,
        "category": "【家庭修行・包容做家事】",
        "quote": "「在家做家事全盤包容去做，不計較職責；天官仙佛在看，自會圓滿安排。」",
        "detail": "不要在家裡爭論這是誰的工作、誰該洗碗倒垃圾。抱著包容感恩的心默默全盤去做，仙佛天官都會為你做功德紀錄，時機成熟自然會讓家人看見並轉化氛圍。"
    },
    {
        "id": 32,
        "category": "【人生及格線・三分之一定律】",
        "quote": "「人生成功三分之一定律：家庭、健康、事業，三選二就60分及格！」",
        "detail": "家庭成功佔1/3、健康成功佔1/3、事業成功佔1/3。能把身體顧好、家庭應對得當，就已經完成六成及格了！不要用負面心情看待家庭摩擦，菩薩是在藉此成全孝道。"
    },
    {
        "id": 33,
        "category": "【至霈心得・不批判多稱讚】",
        "quote": "「不要去批判他人，批判只會成為自己的負能量；多真誠讚美旁人。」",
        "detail": "批判他人只會把自己的心念弄濁。多看別人的亮點、真誠讚揚；自己帶頭改善習氣、勇於承擔，旁人看在眼裡也會更加積極，攜手達到共好境界。"
    },
    {
        "id": 34,
        "category": "【建智體悟・化繁為簡】",
        "quote": "「處理事情的方法越直接簡單，就不會想太多，重點在後續執行。」",
        "detail": "事情想得太複雜往往是自己給自己設置太多假設障礙。找到最直接核心的方法就專心去執行，元神在踏實行動中自然獲得極大的安定與喜悅，自信由此而生。"
    },
    {
        "id": 35,
        "category": "【日常習慣・善用便利貼】",
        "quote": "「善用便利貼與隨身筆記本，別人交代的職責第一時間寫下。」",
        "detail": "粗心忘東忘西往往是因為心思只聚焦在自己感興趣的事上。隨身攜帶小筆記本與便利貼，別人交代的事項隨手寫下並貼在顯眼處，養成做事滴水不漏的好習慣。"
    },
    {
        "id": 36,
        "category": "【人際相處・真誠讚美】",
        "quote": "「真誠誇獎要說得出具體優點，互相加油打氣，成就彼此。」",
        "detail": "敷衍的客套話無法打動人心。細心觀察身邊同修與朋友的具體付出與長處，真誠說出：『我覺得你這件事處理得很細心！』用正向言語建立良性互助的能量場。"
    },
    {
        "id": 37,
        "category": "【口德修養・不言人過】",
        "quote": "「不該講的話不能講，不要去講人家的錯誤；多看優點包容短處。」",
        "detail": "修行人不可把道場或工作場合變成八卦是非地。言語要懂得分寸與留白，不當面給人難堪，不在背後妄議是非，守口慎言就是守護自己內在的清靜。"
    },
    {
        "id": 38,
        "category": "【心法根基・起心動念】",
        "quote": "「所有事情的根源都在起心動念，念頭一動，因果就開始流轉。」",
        "detail": "外在的世界只是內在心念的鏡子。時時刻刻觀照自己的每一個起心動念：這一念是出於慈悲還是自私？是感恩還是怨懟？隨時把偏差的念頭拉回正軌。"
    },
    {
        "id": 39,
        "category": "【心態修煉・境隨心轉】",
        "quote": "「不要被眼前的外境牽著走；境隨心轉，而非心隨境轉。」",
        "detail": "心若亂了，外在做什麼事情都會跟著錯位失衡。遇到困境逆境時，先穩住自己的呼吸與心神，心安定了、智慧清澈了，外在的環境自會隨著你的氣場轉化。"
    },
    {
        "id": 40,
        "category": "【情緒修煉・不能大於仙佛】",
        "quote": "「情緒大於仙佛的時候很可惜，因為機緣不是每次都有。」",
        "detail": "當人的脾氣與情緒上來時，往往會把仙佛的靈感與貴人的提點硬生生擋在門外。察覺到情緒躁動時，趕緊做幾次深呼吸、靜坐片刻，莫讓一時的人性情緒壞了一生的殊勝道緣。"
    },
    {
        "id": 41,
        "category": "【真理與煩惱・為我好定義】",
        "quote": "「活在相裡就會產生煩惱；把大家對我的行為全部定義成『為我好』。」",
        "detail": "『為我好』就是無上的真理與解脫濾鏡。別人讚美我是鼓勵我，別人挑剔我是雕塑我，遇到逆境挫折也是在幫我消業消災。抱著感恩的心，煩惱無從著落。"
    },
    {
        "id": 42,
        "category": "【轉念智慧・換位思考】",
        "quote": "「遇到不想做的事，換個角度問：我要怎樣才會想做？怎樣能不讓對方反感？」",
        "detail": "不要陷在排斥與對立的牛角尖裡。轉變思考的方向，探索能讓雙方都感到舒服的模式；把消極的『我不想』轉化為積極的『我可以如何圓滿做好』。"
    },
    {
        "id": 43,
        "category": "【寬心智慧・給自己留緩衝】",
        "quote": "「不要給自己太多壓力；有緩衝、喘口氣，頭腦才能轉動。」",
        "detail": "你本來就很棒，不需要時刻把自己逼到極限。給心靈留一點彈性與餘裕，學會適時放鬆喘口氣，心平氣和了，大腦的應變智慧自然泉湧而出。"
    },
    {
        "id": 44,
        "category": "【放下執念・驗證童年】",
        "quote": "「要把小時候的自己放下；當你成功以後，才能真正驗證小時候的自己。」",
        "detail": "不要一直困在過去的委屈、執著或童年的陰影中。向前看、活在當下，把眼前的事做好；當你在現實世界立足成功了，過去的一切經歷才會成為有意義的資糧。"
    },
    {
        "id": 45,
        "category": "【生活禪意・吃飯專心吃飯】",
        "quote": "「配合地球人的大腦，生活單純化；吃飯就專心吃飯，不要想那麼久。」",
        "detail": "很多人吃飯時想著工作，工作時想著煩惱，整天腦袋空轉耗損心神。把複雜的心境單純化，吃飯就好好品嚐每口飯菜，給自己一個純淨放空的當下，生活自然輕鬆自在。"
    },
    {
        "id": 46,
        "category": "【修行心態・師父只是指路】",
        "quote": "「不要把師父當成依賴的靠山；師父是指路人，修行的路還是要自己走。」",
        "detail": "師父給的是航海圖與燈塔，真正掌舵划船穿越風浪的人必須是自己。不要期待仙佛或師父替自己背負一切功課，拿出自己的力量與擔當，一步一腳印走穩自己的人生路。"
    },
    {
        "id": 47,
        "category": "【健康根本・身為修行的器皿】",
        "quote": "「身體一定要顧好；身是修行的器皿，器皿壞了，再多功課都裝不下。」",
        "detail": "沒有健康的體魄，再高遠的抱負與修行願力都成了空中樓閣。規律作息、充足睡眠、適度活動，好好愛惜仙佛賜予的這個肉身載具，它是你行功立德最重要的器皿。"
    },
    {
        "id": 48,
        "category": "【靈性修煉・識神放空】",
        "quote": "「識神放空，讓內在純淨的元神顯發出來去渡人、去處世。」",
        "detail": "腦袋裡雜亂的念頭、算計與擔憂都是後天的識神在作祟。遇到複雜的人事問題，先把識神的喋喋不休按暫停鍵，讓內在純真、光明、本自具足的元神智慧當家作主。"
    },
    {
        "id": 49,
        "category": "【靈性喜悅・元神充實】",
        "quote": "「當你願意整理智慧筆記、付出渡人，元神會非常喜悅，越做越有動力。」",
        "detail": "元神最渴望的是智慧的提升與利他的奉獻。當你投入整理智慧心得、幫助他人解開生命困惑時，元神會得到深層的滋養與充電，心中充滿充沛的法喜與成就感。"
    },
    {
        "id": 50,
        "category": "【能量淨化・玉皇真經與充電】",
        "quote": "「感到負面磁場干擾，唸玉皇真經或至大廟敬拜站5分鐘，請仙佛充電。」",
        "detail": "敏感體質的人容易吸收大環境中的負面情緒與穢氣。感到沉重時，靜心誦念玉皇真經，或走到正神大廟的天公爐前放空靜站五分鐘，祈請有緣仙佛為身心灌注純陽清氣。"
    },
    {
        "id": 51,
        "category": "【護法神威・關聖帝君作主】",
        "quote": "「覺得磁場嚴重不對勁時，祈求法門護法神關聖帝君作主庇佑。」",
        "detail": "我們法門的護法神是正氣浩然的關聖帝君。若遇到嚴重的負能量侵擾或心中產生恐懼不安，恭敬祈請帝君聖駕降臨作主，斬斷無形糾纏，保佑元神安泰清朗。"
    },
    {
        "id": 52,
        "category": "【安定心神・滴水觀音與靈坐】",
        "quote": "「拋開煩躁思緒、元神安定，祈請無極滴水觀世音菩薩協助，靈坐修心。」",
        "detail": "心浮氣躁、被外界瑣事牽動心弦時，點一炷清香或閉目靈坐五到十分鐘。祈請大慈大悲滴水觀音甘露遍灑，化解焦躁戾氣，提升對人事的慈悲與同理心。"
    },
    {
        "id": 53,
        "category": "【守護磁場・遠離靈性雜片】",
        "quote": "「大環境負能量重，跟無形或靈性提升無關的獵奇影片不要看。」",
        "detail": "網絡上充斥許多鬼神獵奇、負面宣傳的影片，隨便看幾秒鐘就容易產生頻率共振、引來負面陰氣干擾。保護好自己的精神眼界，不看、不聽、不想，只專注在正法正念的學習上。"
    },
    {
        "id": 54,
        "category": "【處事態度・主動回報安心】",
        "quote": "「不管有緣人的回應是什麼，包含考慮看看，都要主動回報讓師長安心。」",
        "detail": "做事情有始有終、前後呼應，這是修道人最基本的信譽。即使對方沒有立即答應或態度猶豫，也主動向組長與師長回報進展，展現尊師重道與負責任的行事風範。"
    },
    {
        "id": 55,
        "category": "【心態光明・主動用心修學】",
        "quote": "「放大光明才有辦法成功；身為弟子要主動關心，修就是要常來上課。」",
        "detail": "不用預設立場覺得師父很忙而不敢打擾。有心修學，就該主動關心師長、主動參加每一次智慧課程。做表面的沒有用，把內心的光芒放大，坦蕩真誠地走入道場與人群。"
    },
    {
        "id": 56,
        "category": "【智慧真意・知日與心豐】",
        "quote": "「『智』是知日通達大道；『慧』是心思純淨不繁雜。追隨智慧眾仙助。」",
        "detail": "『智』代表天上的智慧與光明之日；『慧』中有豐，代表不要讓心思如繁草般雜亂無章。心思純淨、一心向道，眾仙佛與貴人自然會從四面八方前來護持助你圓滿。"
    },
    {
        "id": 57,
        "category": "【事業智慧・沉得住氣】",
        "quote": "「急了之後哪怕有案子也會困難重重；要沉得住氣，穩穩來。」",
        "detail": "心態急躁時，做決策往往漏洞百出，容易遭人蒙騙甚至破財賠錢。越是面對困難或機會，越要沉著冷靜、按部就班，把每一個環節落實打磨好，生意事業自然細水長流。"
    },
    {
        "id": 58,
        "category": "【一人公司・服務與SOHO】",
        "quote": "「一人公司的發展，朝SOHO與服務業方向踏實前進，發揮獨特價值。」",
        "detail": "一人創業不需要好高騖遠追求龐大編制。專注發揮自己最擅長的專業服務，把每一個登門的客戶當作有緣人細心對待，建立深厚口碑與信任，路自然越走越寬廣。"
    },
    {
        "id": 59,
        "category": "【創業心法・創業渡人並進】",
        "quote": "「會渡人，創業也會成功；創業與渡人要並進，遇到問題積極請教。」",
        "detail": "渡人本質上就是深入理解人性、幫助對方解開困頓的過程，這與做好一家企業的核心完全一致。把助人的善念融入商業服務之中，遇到瓶頸積極向前輩請益，事業與功德相輔相成。"
    },
    {
        "id": 60,
        "category": "【處世透徹・人事總有一個缺】",
        "quote": "「人事都會有一個缺，世間沒有真正圓滿；天時地利人和佔兩個就可成。」",
        "detail": "不要因為事情存在一點點瑕疵或遺憾就灰心喪氣。世間本是殘缺中見美麗，只要佔了天時、地利、人和中的兩項，就大有可為。把做對的事記下來，堅持到底。"
    },
    {
        "id": 61,
        "category": "【推拿事業・也要神也要人】",
        "quote": "「推拿以健康為本，發揮專業同時祈請仙佛加持；也要神，也要人。」",
        "detail": "人事盡到了極致，再加上神佛的無形庇佑，就是所向披靡的雙管齊下。手法上要精益求精、虛心修正習慣；心態上祈請仙佛慈光加被，讓客戶在調理中獲得身心靈的全面療癒。"
    },
    {
        "id": 62,
        "category": "【服務本色・對人不要敷衍】",
        "quote": "「對人不要敷衍，人家有事請我幫忙要盡心盡力；那個真心就是價值。」",
        "detail": "客戶與朋友能感受到你的每一分用心程度。不論事情大小，只要答應了就全心以赴，把對方的託付當成自己的事。那份毫無算計的真誠，就是千金難買的品牌信譽。"
    },
    {
        "id": 63,
        "category": "【超脫世俗・做好自己超越虛實】",
        "quote": "「不要管虛實，把自己做好；天上的功果、人間的福報都跟自己有關。」",
        "detail": "外界的真真假假、評頭論足都不需太過在意。守住自己的良心與道心，在人間踏實付出累積福報，在天界累積清淨功果，這些都是誰也奪不走的真實收穫。"
    },
    {
        "id": 64,
        "category": "【執行策略・一次抓兩到三個重點】",
        "quote": "「做事一次要抓兩到三個重點；以前只抓一個，容易顧此失彼導致失衡。」",
        "detail": "人生不能偏廢。只顧賺錢容易失掉健康，只顧理想容易忽略現實。學會在生活中同時平衡事業、修行與家庭，一次掌握兩到三個關鍵核心，人生這座天平才能穩若磐石。"
    },
    {
        "id": 65,
        "category": "【外在展現・氣色衣裝好運來】",
        "quote": "「人要衣裝整齊，氣色要好，才不會活在自己的封閉世界裡。」",
        "detail": "氣色是內在能量與精氣神的外在顯影，也是衣裝的重要一環。把自己整理得乾淨清爽、昂首挺胸走入人群，好的人緣、貴人與財氣自然會被你的正面氣場吸引過來。"
    },
    {
        "id": 66,
        "category": "【投資心態・切忌盲目與凹單】",
        "quote": "「投資失敗大多是心態問題：盲目自信、不認錯、凹單；切忌急躁貪念。」",
        "detail": "很多人小賺就得意忘形、重壓下注，虧損了卻不肯認錯硬凹，最終落得大賠離場。投資如修身，必須克制內心的貪婪與傲慢，心態平靜了，才能客觀看清市場的起落規律。"
    },
    {
        "id": 67,
        "category": "【嚴格風控・果斷設定停損】",
        "quote": "「股票操作絕不可凹單，一定要設定好停損；以週期思維冷靜觀察。」",
        "detail": "市場永遠是對的，承認看錯並不可恥，及時停損才能保住元氣。不抱僥倖賭博的心態，以三個月以上的長遠週期穩健觀察，嚴格遵守紀律，才能在金錢浪潮中立於不敗之地。"
    },
    {
        "id": 68,
        "category": "【金錢哲學・流動的能量】",
        "quote": "「錢財是流動的能量，該用就用、該省就省；不取非分之財，財路自穩。」",
        "detail": "不要做金錢的奴隸。把錢用在正途、用在提升智慧與利益眾生上，它就是光明的甘露；守住清廉品格，不貪非分非義之財，內在平靜安寧，命中該有的福祿自然如泉水般源源而來。"
    },
    {
        "id": 69,
        "category": "【功果相應・收穫多少護持多少】",
        "quote": "「收穫多少就護持多少；踏實累積陰德與功果，福報如影隨形。」",
        "detail": "得到多少恩惠與收穫，就抱著同等甚至加倍的感恩心回饋給道場與社會。不計較一時的得失，默默行善積陰德，天官明鏡高懸，播撒下的善種子終將在生命中綻放美麗的花果。"
    },
    {
        "id": 70,
        "category": "【堅定信仰・信念如磐石】",
        "quote": "「心如髮絲容易受外境牽動，所以信念要足；守住正道，永不退轉。」",
        "detail": "凡人的心念常常像一根細髮般脆弱，外界一句流言蜚語或一點挫折就能掀起滔天巨浪。因此信念必須深植於真理與大道之中，像磐石一樣堅定不移，任憑狂風暴雨吹打，本心始終安住清澈。"
    }
];

  var currentWisdomIndex = 0;

  function renderWisdomCard(idx) {
    if (idx < 0) idx = WISDOM_CARDS.length - 1;
    if (idx >= WISDOM_CARDS.length) idx = 0;
    currentWisdomIndex = idx;

    var card = WISDOM_CARDS[currentWisdomIndex];
    if (!card) return;

    if (dom.wisdomCategory) dom.wisdomCategory.innerHTML = card.category;
    if (dom.wisdomQuote) dom.wisdomQuote.innerHTML = card.quote;
    if (dom.wisdomDetail) dom.wisdomDetail.innerHTML = card.detail.replace(/\n/g, "<br>");
    if (dom.wisdomCounter) dom.wisdomCounter.innerHTML = "卡片 " + (currentWisdomIndex + 1) + " / " + WISDOM_CARDS.length;

    if (dom.wisdomCard) {
      dom.wisdomCard.className = "wisdom-deck-box anim-pop";
      setTimeout(function() {
        if (dom.wisdomCard) dom.wisdomCard.className = "wisdom-deck-box";
      }, 300);
    }
  }

  function drawNextWisdomCard() {
    var nextIdx = (currentWisdomIndex + 1) % WISDOM_CARDS.length;
    renderWisdomCard(nextIdx);
  }

  function drawRandomWisdomCard() {
    var randomIdx = Math.floor(Math.random() * WISDOM_CARDS.length);
    if (randomIdx === currentWisdomIndex && WISDOM_CARDS.length > 1) {
      randomIdx = (randomIdx + 1) % WISDOM_CARDS.length;
    }
    renderWisdomCard(randomIdx);
  }

  function setupWisdomModule() {
    if (dom.wisdomCard) {
      dom.wisdomCard.onclick = function() {
        drawNextWisdomCard();
      };
    }
    if (dom.btnWisdomNext) {
      dom.btnWisdomNext.onclick = function(e) {
        if (e && e.stopPropagation) e.stopPropagation();
        drawNextWisdomCard();
      };
    }
    if (dom.btnWisdomRandom) {
      dom.btnWisdomRandom.onclick = function(e) {
        if (e && e.stopPropagation) e.stopPropagation();
        drawRandomWisdomCard();
      };
    }
    renderWisdomCard(0);
  }

  // Initialization
  function init() {
    initDomCache();

    updateClock();
    setInterval(updateClock, 1000);

    fetchWeather();
    setInterval(fetchWeather, 300000); // every 5 min

    fetchStocks();
    setInterval(fetchStocks, 60000); // every 60 sec

    fetchMessages();
    setInterval(fetchMessages, 60000); // every 60 sec

    setupMusicPlayer();
    setupRadioPlayer();
    setupGuidanceModule();
    setupWisdomModule();
    setupMessageForm();
    setupThemeSwitcher();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
