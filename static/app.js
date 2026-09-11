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
    // 互斥：暫停本機 MP3 播放器
    pauseTrack();

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
    setupMessageForm();
    setupThemeSwitcher();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
