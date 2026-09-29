+++
title = "Please don't create unnecessary abstractions"
date = 2016-02-27
aliases = ["/posts/external/por-favor-nao-crie-abstracoes-desnecessarias/"]
[taxonomies]
tags = ["software-engineering", "architecture", "laravel", "php", "medium"]
[extra]
source = "medium"
original_url = "https://gabrielkoerich.medium.com/por-favor-n%C3%A3o-crie-abstra%C3%A7%C3%B5es-desnecess%C3%A1rias-96e97ad2a51b"
+++

The last time I saw a discussion about laravel I was a little scared. People seem to take the abstraction part very seriously and want to create completely unnecessary interfaces and classes.

The question was about creating a `PostRepositoryInterface`, this would just be an abstraction for the standard class, `PostEloquentRepository`, which in this case is a wrapper for the `Post` model methods. There are several tutorials out there actually telling you to do this, because “one day” “maybe” you “may” want to change your persistence layer to use Mongo or change your ORM. Is it really?

The idea of creating a repository for the model is interesting. As the project grows, the model may end up becoming too large and difficult to maintain. To avoid repetitions in the controller, it is a good practice to create methods that will be used in different places in the project in the corresponding repository.

The problem is when this becomes an unnecessary abstraction. What is the use of a `PostRepositoryInterface`, which will bring an instance of the `PostEloquentRepository`? Will your implementation one day change? Nobody usually changes the database type (relational/non-relational) or ORM in the middle of a project. And even then, if you change, just change the class and that's it? Of course not. You know I don’t.

I always assume that we should do as little code as possible in the first iteration. Do not abstract into multiple interfaces that will only have a single implementation or other unnecessary classes. In the future, it is much better to change something simple and transform it into more robust logic than having to maintain an absurd abstraction that you no longer remember the meaning or reason for doing it.

And I say this because I've already made this mistake a lot. Having read many books on software development principles, I thought that everything had to be taken completely to the letter. But that doesn't always make sense. In the end, I ended up creating a lot of classes and interfaces just because it seemed like the right thing to do.

Someone could still argue that all this abstraction is simply to be able to change the implementation in the tests and not reach any persistence layer or something like that. Okay, it might be. But is this trade-off worth it? And, in my opinion, these tests that use mocks in all dependencies end up testing practically nothing. They only serve as tests for typing errors. In this case, I prefer integration tests that actually do what a user would do on the production server.

So please. Create abstractions only when they are necessary. Do you know when they will be needed? When you create a method/class with a typehint and it accepts more than one implementation as a parameter/dependency. In this case, it is not only valid to create interfaces, but mandatory. When your application grows (we hope it will), you won't want to have a monster, but rather something simple that can have its complexity changed quickly, without much stress.

*Originally published on [Medium](https://gabrielkoerich.medium.com/por-favor-n%C3%A3o-crie-abstra%C3%A7%C3%B5es-desnecess%C3%A1rias-96e97ad2a51b)*
