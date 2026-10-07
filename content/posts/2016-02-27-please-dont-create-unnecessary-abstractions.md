+++
title = "Please don't create unnecessary abstractions"
date = 2016-02-27
aliases = ["/posts/external/por-favor-nao-crie-abstracoes-desnecessarias/"]
[taxonomies]
tags = ["software-engineering", "architecture", "laravel", "medium"]
[extra]
source = "medium"
original_url = "https://gabrielkoerich.medium.com/por-favor-n%C3%A3o-crie-abstra%C3%A7%C3%B5es-desnecess%C3%A1rias-96e97ad2a51b"
+++

The last time I saw a discussion about Laravel, it scared me a little. People take abstraction very seriously and want to create interfaces and classes that nobody needs.

The question was about creating a `PostRepositoryInterface`. It would only be an abstraction over the default class, `PostEloquentRepository`, which in this case wraps the `Post` model methods. Several tutorials out there tell you to do exactly this, because "one day" you "may" want to move your persistence layer to Mongo or switch your ORM. Really?

A repository for the model is a good idea. As the project grows, the model can get too big and hard to maintain. To avoid repeating code in the controllers, put the methods you use in several places in the matching repository.

The problem starts when this turns into an abstraction nobody needs. What is a `PostRepositoryInterface` for, if all it does is hand you an instance of `PostEloquentRepository`? Will your implementation ever change? Almost nobody switches database type (relational or non-relational) or ORM in the middle of a project. And if you do, is changing one class all it takes? Of course not. I know it isn't.

I always start from the idea that the first iteration should have as little code as possible. Don't add interfaces that will only ever have one implementation, or other classes you don't need. Later, it is much easier to take something simple and grow it into something more complete than to maintain an absurd abstraction when you no longer remember what it was for or why you wrote it.

I say this because I made this mistake many times. I had read many books on software design principles, and I thought everything had to be followed to the letter. That doesn't always make sense. I ended up creating lots of classes and interfaces just because it felt like the right thing to do.

Someone could still argue that all this abstraction exists so you can swap the implementation in tests and never touch the persistence layer. Fine, maybe. But is the trade-off worth it? In my opinion, tests that mock every dependency end up testing almost nothing. They only catch typos. I prefer integration tests that do what a user would actually do on the production server.

So please, create abstractions only when you need them. How do you know when you need one? When a method or class takes a typehinted parameter or dependency that has more than one implementation. Then an interface is more than valid, it is required. When your application grows (we hope it will), you don't want a monster. You want something simple whose complexity you can change quickly, without much stress.

*Originally published on [Medium](https://gabrielkoerich.medium.com/por-favor-n%C3%A3o-crie-abstra%C3%A7%C3%B5es-desnecess%C3%A1rias-96e97ad2a51b)*
