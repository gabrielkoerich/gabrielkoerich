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

![Bulldesk logo over an office](/images/posts/simple-workflow-with-laravel-a-look-behind-bulldesk.jpeg)

This is one of those posts that I've been planning to do for a long time, but always ended up putting off.

Every now and then I get asked about the technologies behind Bulldesk and what the workflow is like to develop it. The stack behind the project is simple, but let's take it in parts.

#### PHP 7 + Laravel

I've been in love with this framework since I discovered it in 2012. It was still in version 3 and it's absurd how much it's evolved. At the time it was a bit of a gamble, but as I already knew and admired Symfony and knew that several components had been used by Laravel since then, it wasn't such a difficult choice after the “end” of CodeIgniter.

PHP 7 was released in December, I didn't have much patience and I already updated the production server in January. It wasn't that risky due to the fact that tests had already been running on 7.0 since 2015 through Travis. The performance gain was interesting, but nothing absurd.

#### VueJS + Laravel Elixir

Vue is the simplest to use JavaScript framework (yes, another one) I've ever seen. It's fast, light and intuitive. I've never liked the front as much as I do today.

Oh, and of course I couldn't help but mention Laravel Elixir, it is a “facilitator” for Gulp. With it, my `gulpfile.js` has only 35 fucking lines! It's very beautiful.

#### Local development with Homestead

In larger projects, it is essential to have the same production configuration in the development environment. This is simple using Vagrant and Homestead.

In the case of bulldesk we still use node.js for real-time notifications, Memcached for caching, Redis for sessions and Beanstalkd for queues. Having to install all of this by hand would be quite annoying and Homestead helps with that.

It's still not the easiest or fastest thing in the world to install and configure, perhaps that's why Taylor has launched Laravel Valet now, but that's something for another article.

#### Deploy with Laravel Forge + Digital Ocean

I don't even have words for how beautiful this combo is. I've used Digital Ocean before, but it's very tedious to create a server and configure it from scratch.

In Bulldesk, all tasks that do not need to return a message to the user immediately are done by queues running in the background. This includes the entire automation, campaigns and email marketing part.

Through Forge it is possible to start and stop workers, in addition to deploying via github, configuring nginx, firewall, network, SSL and other things. And when I need to create a new server, it does everything for me. Very useful in the entire DevOps process.

#### Backup on Amazon, logs on papertrail, errors on Busgnag

Backups are automatically made to Amazon twice a day.

The entire log of what happens in the application is sent to Papertrail. It is much easier to analyze and see what happens in real time. No need to ssh into the server to see what happened.

And, when an exception appears, it automatically goes to Busgnag. He's the one who wakes me up when something bad happens.

#### That's all.

Or at least that's what I remember now.

It's always interesting to share these things to also see what is being used in other projects.

And you, would you do something different?

*Originally published on [Medium](https://gabrielkoerich.medium.com/simples-workflow-com-laravel-uma-vis%C3%A3o-por-tr%C3%A1s-do-bulldesk-8a781e1a7684)*
