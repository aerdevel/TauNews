const toggle = document.querySelector(".menu-toggle");
const mobileNav = document.querySelector(".mobile-nav");

if (toggle && mobileNav) {
  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    mobileNav.hidden = isOpen;
  });
}

// Кнопки редактора вставляют Markdown в выделенный фрагмент или позицию курсора.
const markdownEditor = document.querySelector(".markdown-source");
const markdownToolbar = document.querySelector(".markdown-toolbar");

if (markdownEditor && markdownToolbar) {
  markdownToolbar.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-prefix]");
    if (!button) return;

    const start = markdownEditor.selectionStart;
    const end = markdownEditor.selectionEnd;
    const selected = markdownEditor.value.slice(start, end);
    const content = selected || button.dataset.placeholder || "текст";
    const prefix = button.dataset.prefix || "";
    const suffix = button.dataset.suffix || "";
    const replacement = `${prefix}${content}${suffix}`;

    markdownEditor.setRangeText(replacement, start, end, "select");
    markdownEditor.focus();
  });
}
