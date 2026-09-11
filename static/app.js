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
    setupMessageForm();
    setupThemeSwitcher();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
