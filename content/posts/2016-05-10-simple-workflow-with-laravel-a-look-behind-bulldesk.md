+++
title = "Simple workflow with Laravel, a look behind Bulldesk"
date = 2016-05-10
aliases = ["/posts/external/simples-workflow-com-laravel-uma-visao-por-tras-do-bulldesk/"]
[taxonomies]
tags = ["bulldesk", "laravel", "php", "devops", "software-engineering", "medium"]
[extra]
source = "medium"
original_url = "https://gabrielkoerich.medium.com/simples-workflow-com-laravel-uma-vis%C3%A3o-por-tr%C3%A1s-do-bulldesk-8a781e1a7684"
+++

<img src="{{ asset(path="images/posts/simple-workflow-with-laravel-a-look-behind-bulldesk.jpeg") }}" alt="Bulldesk logo over an office">

I've been meaning to write this post for a long time and kept putting it off.

Every now and then someone asks me what technology runs Bulldesk and what my workflow looks like. The stack is simple, so let's go piece by piece.

#### PHP 7 + Laravel

I've loved this framework since I found it in 2012. It was on version 3 back then, and it's absurd how much it has grown. Picking it was a bit of a gamble at the time. I already knew and admired Symfony, though, and Laravel used several Symfony components, so after CodeIgniter "ended" the choice wasn't that hard.

PHP 7 came out in December. I didn't have much patience, so I upgraded the production server in January. It wasn't much of a risk, because the tests had been running on 7.0 in Travis since 2015. The speedup was nice, but nothing absurd.

#### VueJS + Laravel Elixir

Vue is the easiest JavaScript framework (yes, another one) I've ever used. It's fast, light and intuitive. I've never enjoyed frontend work as much as I do now.

And of course I have to mention Laravel Elixir, a "helper" for Gulp. With it my `gulpfile.js` has only 35 fucking lines! It's beautiful.

#### Local development with Homestead

On bigger projects the development environment has to match production. Vagrant and Homestead make that simple.

At Bulldesk we also run node.js for real-time notifications, Memcached for caching, Redis for sessions and Beanstalkd for queues. Installing all of that by hand would be a pain, and Homestead takes care of it.

It's still not the easiest or fastest thing to install and set up, which may be why Taylor just launched Laravel Valet, but that's a topic for another post.

#### Deploy with Laravel Forge + Digital Ocean

I don't even have words for how good this combo is. I had used Digital Ocean before, but creating a server and setting it up from scratch is tedious.

At Bulldesk, every task that doesn't need to answer the user right away goes to a queue that runs in the background. That covers all the automation, campaigns and email marketing.

Forge starts and stops workers, deploys from GitHub, and configures nginx, the firewall, the network, SSL and more. When I need a new server, it does everything for me. It saves a lot of work across the whole DevOps side.

#### Backups on Amazon, logs on Papertrail, errors on Bugsnag

Backups go to Amazon automatically twice a day.

Every log line from the app goes to Papertrail, which makes it much easier to follow what's happening in real time. I don't need to ssh into the server to find out what happened.

When an exception shows up, it goes straight to Bugsnag. Bugsnag is the one that wakes me up when something breaks.

#### That's all

Or at least that's all I can remember right now.

I like sharing this kind of thing because it shows me what other projects use too.

What would you do differently?

*Originally published on [Medium](https://gabrielkoerich.medium.com/simples-workflow-com-laravel-uma-vis%C3%A3o-por-tr%C3%A1s-do-bulldesk-8a781e1a7684)*
