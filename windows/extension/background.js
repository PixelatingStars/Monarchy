chrome.runtime.onMessage.addListener((message, _sender, respond) => {
  let endpoint = null;
  let body = null;
  if (message?.type === "monarchy-channel-state") {
    endpoint = "channel";
    body = message.channel;
  } else if (message?.type === "monarchy-server-link" && typeof message.url === "string") {
    endpoint = "join";
    body = message;
  } else {
    return false;
  }
  fetch(`http://127.0.0.1:17381/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  }).then(response => respond({status: response.status}))
    .catch(() => respond({status: 0}));
  return true;
});
