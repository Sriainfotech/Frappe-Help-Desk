import { io } from "socket.io-client";

// extend window object
declare global {
  interface Window {
    site_name: string;
  }
}

export function initSocket() {
  let host = window.location.hostname;
  let siteName = window.site_name || host;
  // HD Task module / docker: connect same-origin so nginx proxies /socket.io to the websocket
  // service, instead of dialing the unpublished socketio_port (9000) on the host.
  let url = `${window.location.origin}/${siteName}`;

  const socket = io(url, {
    withCredentials: true,
    reconnectionAttempts: 5,
  });

  // socket.io-client destroys the socket on a server-side connect_error, which shows up in the
  // browser only as "WebSocket is closed before the connection is established"; surface the reason.
  socket.on("connect_error", (err) => {
    console.warn("[socket] connect_error:", err.message);
  });

  return socket;
}

export const socket = initSocket();
