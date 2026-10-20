+++
title = "My 'quake' Ghostty terminal"
date = 2026-10-20
description = "After 10 years on iTerm I moved to Ghostty: a drop-down terminal on one global shortcut, with native tabs, tmux, and no useless title row on top."
[taxonomies]
tags = ["ghostty", "terminal", "tmux", "macos", "dotfiles", "zsh"]
+++

After 10 years, I finally retired iTerm as my main terminal. After a few months of trying, I got to a Ghostty config I enjoy using. It opens with my main shortcut without the quick terminal, which doesn't support native tabs, and I use native tabs to keep one session per tab.

What annoyed me the most was a useless top row that only said 'zsh'. Whatever I tried, it stayed there, but after a while I got it the way I wanted. It works well and is faster than iTerm was. Here's my [current config](https://github.com/gabrielkoerich/dotfiles/blob/8414d1a706af152150eefea40557adaf1bc2ee34/home/.config/ghostty/config):

```ini
# Shell
shell-integration = zsh
command = /bin/zsh -l -c '"$HOME"/.tmux/tmx'
confirm-close-surface = false

# Font
font-family = JetBrains Mono
font-size = 12

adjust-cell-height = 20%

# Cursor
cursor-style = block
adjust-cursor-height = 20%
mouse-hide-while-typing = true

# Window
window-width = 999
window-height = 45
window-step-resize = false
window-position-x = 0
window-position-y = 0
window-padding-balance = false
window-padding-color = background
window-decoration = true

### macos
macos-hidden = always
macos-titlebar-style = tabs
macos-window-buttons = hidden
macos-titlebar-proxy-icon = hidden

### shell integrations
shell-integration-features = no-title

### Keybindings
keybind = global:shift+cmd+t=toggle_visibility
keybind = ctrl+a>n=next_tab
keybind = ctrl+a>p=previous_tab
keybind = super+r=reload_config

# Colors
palette =  0=#141414
palette =  8=#666666

palette =  1=#f38ba8
palette =  9=#f38ba8

palette =  2=#a6e3a1
palette = 10=#a6e3a1

palette =  3=#f9e2af
palette = 11=#f9e2af

palette =  4=#89b4fa
palette = 12=#89b4fa

palette =  5=#cba6f7
palette = 13=#cba6f7

palette =  6=#94e2d5
palette = 14=#94e2d5

palette =  7=#cccccc
palette = 15=#cccccc

background = #000000
background-opacity = 0.9
background-blur = 20
foreground = #cccccc
cursor-color = #cccccc
selection-background = #282828
selection-foreground = #cccccc
```

> PS: the GitHub version has more in it, because I'm testing everything that can improve my workflow.

This only works with zsh, [tmx](https://github.com/gabrielkoerich/dotfiles/blob/8414d1a706af152150eefea40557adaf1bc2ee34/home/.tmux/tmx), my whole tmux config and all its integrations. I'm not a tmux expert, but I **think** this is the part that did the job:

```bash
# Enable terminal title setting
set -g set-titles on

# Send user@host and the session name (#S) up to Ghostty as the window title
set -g set-titles-string "#(whoami)@#H 👻 #S"

set-option -g automatic-rename on
set-option -g automatic-rename-format '#(whoami)@#H 👻 #S'
```

This config is also available [here](https://github.com/gabrielkoerich/dotfiles/blob/8414d1a706af152150eefea40557adaf1bc2ee34/home/.tmux.conf).

It looks like this, just the way my old iTerm setup looked:

[![](/images/posts/ghostty.jpg)](/images/posts/ghostty.jpg)

If you want to see my whole setup, my [dotfiles](https://github.com/gabrielkoerich/dotfiles) repo has everything.

This feels like when I retired Sublime Text for Zed 2 years ago.
