/** Shared by the root layout (server) and the Roaring Lion intro (browser). */
export const INTRO_KEY = "tdl-intro-seen";

/** Runs in <head> before paint: hides the intro when it has already played this session. */
export const INTRO_HEAD_SCRIPT = `try{if(sessionStorage.getItem("${INTRO_KEY}")&&!/[?&]intro=1/.test(location.search))document.documentElement.classList.add("intro-seen")}catch(e){}`;
