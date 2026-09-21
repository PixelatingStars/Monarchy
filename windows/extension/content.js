(() => {
  const PLACE = "15532962292";
  const approved = ["CORRUPTION", "DREAMSPACE", "GLITCH", "CYBERSPACE", "SINGULARITY", "HELL"];
  const completed = new Set();
  const direct = /roblox:\/\/(?:placeID=|experiences\/start\?[^\s"'<>]*placeId=)(\d+)[^\s"'<>]*gameInstanceId=([0-9a-f-]{36})/i;
  const chroma = /https?:\/\/hewa7798\.github\.io\/chromahublink\/?\?[^\s"'<>]*placeId=(\d+)[^\s"'<>]*gameInstanceId=([0-9a-f-]{36})/i;
  const privateLink = /https?:\/\/(?:www\.)?roblox\.com\/games\/(\d+)(?:\/[^?\s"'<>]*)?\?[^\s"'<>]*privateServerLinkCode=([a-z0-9_-]+)/i;
  const share = /https?:\/\/(?:www\.)?roblox\.com\/(?:share|share-links)\?[^\s"'<>]*code=([a-f0-9]{32})[^\s"'<>]*type=Server/i;
  const population = /(?:^|\D)(\d{1,2})\s*\/\s*20(?:\D|$)/;

  function channel() {
    const selected = [...document.querySelectorAll('a[aria-current="page"][href*="/channels/"]')]
      .map(node => node.textContent || node.getAttribute("aria-label") || "").find(text => text.trim());
    const source = (selected || document.title || "").toUpperCase();
    if (source.includes("JESTER")) return {name: "JESTER", kind: "JESTER"};
    if (source.includes("BIOME-SPAWNER")) return {name: "BIOME-SPAWNER", kind: "BIOME"};
    for (const biome of approved) {
      if (source.includes(biome) || (biome === "GLITCH" && source.includes("GLITCHED"))) {
        return {name: biome, kind: "BIOME"};
      }
    }
    return {name: "UNSUPPORTED", kind: "UNSUPPORTED"};
  }

  function linkIn(message) {
    const text = message.textContent || "";
    const candidates = [text, ...[...message.querySelectorAll("a[href]")].map(node => node.href)];
    for (const candidate of candidates) {
      const match = candidate.match(direct) || candidate.match(chroma);
      if (match && match[1] === PLACE) {
        const count = text.match(population);
        return {url: match[0], id: `public:${match[2].toLowerCase()}`,
          playerCount: count ? Number.parseInt(count[1], 10) : null};
      }
      const privateMatch = candidate.match(privateLink);
      if (privateMatch && privateMatch[1] === PLACE) {
        return {url: privateMatch[0], id: `private:${privateMatch[2].toLowerCase()}`, playerCount: null};
      }
      const shareMatch = candidate.match(share);
      if (shareMatch) {
        return {url: shareMatch[0], id: `share:${shareMatch[1].toLowerCase()}`, playerCount: null};
      }
    }
    return null;
  }

  function embeddedBiome(message) {
    const text = (message.textContent || "").toUpperCase();
    if (text.includes("GLITCHED BIOME STARTED") || text.includes("GLITCH BIOME STARTED")) return "GLITCH";
    return approved.find(name => text.includes(`${name} BIOME STARTED`)) || null;
  }

  function scan() {
    const selected = channel();
    chrome.runtime.sendMessage({type: "monarchy-channel-state", channel: selected});
    if (selected.kind === "UNSUPPORTED") return;
    const messages = [...document.querySelectorAll('li[id^="chat-messages-"], [data-list-item-id^="chat-messages"]')];
    let newest = null;
    const snapshot = [];
    for (let index = messages.length - 1; index >= 0; index--) {
      const found = linkIn(messages[index]);
      if (!found || completed.has(found.id)) continue;
      const biome = selected.name === "BIOME-SPAWNER" ? embeddedBiome(messages[index]) : selected.name;
      if (selected.name === "BIOME-SPAWNER" && !biome) continue;
      found.targetBiome = biome;
      snapshot.push(found.id);
      if (!newest) newest = found;
    }
    if (!newest) return;
    chrome.runtime.sendMessage({type: "monarchy-server-link", url: newest.url,
      playerCount: newest.playerCount, targetBiome: newest.targetBiome,
      targetKind: selected.kind, channelName: selected.name}, response => {
      if (response?.status === 202 || response?.status === 208) {
        for (const id of snapshot) completed.add(id);
      }
    });
  }

  new MutationObserver(scan).observe(document.body, {childList: true, subtree: true});
  setInterval(scan, 500);
  setTimeout(scan, 500);
})();
