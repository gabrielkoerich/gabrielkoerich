slidenumbers: true
build-lists: true

# Laravel Architecture, Structure & Standards

---

# What?

- Laravel Structure
- Standards
- Guidelines 
- Tests
- Tips

---

## Laravel Code Struture

---

## The default structure

```bash
/app
├── /Console
|  ├── Kernel.php
├── /Exceptions
|  ├── Handler.php
├── /Http
|  ├── /Controllers
|  ├── /Middleware
|  ├── Kernel.php
├── /Models
|  ├── User.php
├── /Providers
|  ├── AppServiceProvider.php
|  ├── AuthServiceProvider.php
|  ├── BroadcastServiceProvider.php
|  ├── EventServiceProvider.php
|  ├── RouteServiceProvider.php
/bootstrap
/config
/database
/public
/resources
/storage
/tests
```

^
We all start a new project in Laravel all excited and stuff


---

## Cool, right?

---

## But what happens when the project starts to grow?

^
Our project start growing and our models directory become bloated and with lots and lots of classes

---

## The default structure becomes a bloated structure

```bash
/app
├── /Console
|  ├── Kernel.php
├── /Exceptions
|  ├── Handler.php
├── /Http
|  ├── /Controllers
|  ├── /Middleware
|  ├── Kernel.php
├── /Events
|  ├── ActionStarted.php
├── /Jobs
├── /Graphql
├── /Listeners
|  ├── CheckActionShouldRun.php
|  ├── ScheduleNextCampaignAction.php
├── /Mail
├── /Models
|  ├── Action.php
|  ├── RemoteUser.php
|  ├── Campaign.php
|  ├── Category.php
|  ├── Email.php
|  ├── FacebookPage.php
|  ├── FacebookPost.php
|  ├── Template.php
|  ├── TemplateCampaign.php
|  ├── Token.php
├── /Policies
|  ├── ActionPolicy.php
|  ├── CampaignPolicy.php
├── /Providers
|  ├── AppServiceProvider.php
|  ├── AuthServiceProvider.php
|  ├── BroadcastServiceProvider.php
|  ├── EventServiceProvider.php
|  ├── RouteServiceProvider.php
├── /Services
|  ├── ScheduleFacebookPost.php
/bootstrap
/config
/database
/public
/resources
/storage
/tests
``` 

^
This starter example, the project is not that big yet, but it will grow (it couldnt event be produced if was that big), 

^
The problem itself is that you have to open too many different folders to work in a feature

^
The number of files and classes is not the problem here

^
Remember, this is not a good example example is still small, imagine it in a BIG repository

---

## And what can we do to avoid that? 

---

## Better Code Structure and Organization

- Follow Coding Standards 
- PHP FIG PSRs
- Remember that Laravel still is PHP
- Always write tests

^
We have to go back a little here to see some PHP standards

^
Do you know what is PSRs?

^
And you can do whatever you want with PHP, as long as you follow the standards.

^
PHP Framework Interop group

---

### PSR-1: Basic Coding Standard 

- Class names MUST be declared in StudlyCaps.
- Class constants MUST be declared in all upper case with underscore separators.
- Method names MUST be declared in camelCase.

---

### PSR-2: Coding Style Guide

- Code MUST use 4 spaces for indenting, not tabs.
- Control structure keywords MUST have one space after them; method and function calls MUST NOT.
- Opening braces for control structures MUST go on the same line, and closing braces MUST go on the next line after the body.
- Opening parentheses for control structures MUST NOT have a space after them, and closing parentheses for control structures MUST NOT have a space before.

---

### PSR-4: Autoloader

#### Autoloading Spec

| Fully Qualified Class Name    | Namespace Prefix   | Base Directory           | Resulting File Path
| ----------------------------- |--------------------|--------------------------|-------------------------------------------
| \Acme\Log\Writer\File_Writer  | Acme\Log\Writer    | ./acme-log-writer/lib/   | ./acme-log-writer/lib/File_Writer.php
| \Aura\Web\Response\Status     | Aura\Web           | /path/to/aura-web/src/   | /path/to/aura-web/src/Response/Status.php
| \Symfony\Core\Request         | Symfony\Core       | ./vendor/Symfony/Core/   | ./vendor/Symfony/Core/Request.php
| \Zend\Acl                     | Zend               | /usr/includes/Zend/      | /usr/includes/Zend/Acl.php

^
Class autoloading is no magic; they need to follow a standard

----

### PSR-4: How the app directory is autoloaded in Laravel?

```
composer.json
    (...)
    "autoload": {
        "psr-4": {
            "App\\": "app/"
        },
        "classmap": [
            "database/seeds",
            "database/factories"
        ]
    },
```

^
This is where I was trying to get...

^
We can autoload any directory the way we want.

---

##  Namespaces Are Not Just Folders

^
They're not just a folder to throw all classes of that type (like the "Models" folder/namespace)

^
They give meaning and contexts for classes that live inside them

^
They can make we understand better the project itself and boost our productivity


---

##  Laravel is still PHP, remember?

### You can move everything the way you want

^
What can we do?

^
To fix this we need to take a step back and rremember that Laravel is not just Laravel

^
Laravel is PHP and yoou can do whatever you want in PHP

^
You can move any class you want around and just change the namespace

---

# The Contexts Approach

---

# The Contexts Approach

- Think about **No Context Switching**
- Define the **Contexts** of your application
- The "Core" application classes will live in the **Core** namespace
- The less directories (and less classes inside) you need to open to work on something, the better

^
Context switching is not good and is really normal in a big application

^
You don't need to define the contexts before, you'll get them developing the app

^
you'll have the "Campaign" namespace (context) and all that belongs to that "context" lives inside it: models, repositories, services and sometimes, dependending on the size of the project or organization you want to have, even controllers. 

^
The same would be for the "User" namespace, all models and classes to that context will live there. I prefer this then the bloated "Models" namespace with all projects entities (or any other directory).

--- 

### The Contexts Approach Example

```bash
/app
├── /Campaign
|  ├── /Graphql
|  ├── /Model
|  |  ├── Action.php
|  |  ├── Campaign.php
|  |  ├── Category.php
|  |  ├── Template.php
|  |  ├── TemplateCampaign.php
|  ├── /Event
|  |  ├── ActionStarted.php
|  |  ├── ActionCompleted.php
|  ├── /Listener
|  ├── /Policy
├── /Console
|  ├── Kernel.php
├── /Core
├── /Http
|  ├── /Controllers
|  ├── /Middleware
|  ├── Kernel.php
|  ├── RouteServiceProvider.php
├── /User
├── ...User context files
├── /OtherContext
├── ...OtherContext files
├── AppServiceProvider.php
├── EventServiceProvider.php
/bootstrap
/config
/database
/public
/resources
/storage
/tests
``` 

^
You see that in this structure we still have the Http/Controller directory

^
This is a "first stage" move, in the "second stage" we could even move the controller to each context too

^
You can see the AppServiceProvide and EventServiceProvider in the root of the /app

^
You could even have a service provider for a context if needed.

--- 

## We can go deeper and move the Controllers too 

#### Drop the Http namespace & move controllers to each context

```bash
/app
├── /Campaign
|  ├── /Controller
|  ├── /Graphql
|  ├── /Model
|  |  ├── Action.php
|  |  ├── Campaign.php
|  |  ├── Category.php
|  |  ├── Template.php
|  |  ├── TemplateCampaign.php
|  ├── /Event
|  |  ├── ActionStarted.php
|  |  ├── ActionCompleted.php
|  ├── /Listener
|  ├── /Policy
├── /Console
|  ├── Kernel.php
├── /Core
├── /User
├── ...User context files
├── /OtherContext
├── ...OtherContext files
├── AppServiceProvider.php
├── EventServiceProvider.php
├── RouteServiceProvider.php
/bootstrap
/config
/database
/public
/resources
/storage
/tests
``` 
----

### Why Are Tests So Important?

^
Besides giving security and control over your application 

^
Tests allow us to change the structure anyway we want in any stage of the application

^
How would I make a big structure change in a big project without tests? How would I know that things wouldnt break?

---

# Other Laravel Tips

### We should always avoid magic

---

# Drop the Auto Discover feature

```
composer.json
  "extra": {
    "laravel": {
      "dont-discover": [
        "*"
      ]
    }
  }
```

All providers should be explicit registered in the `AppServiceProvider.php`

And not even in the `config/app.php`

---

### Explicit Provider Register

```php
AppServiceProvider.php

    /**
     * The provider class names.
     */
    protected $providers = [
        'default' => [
            /*
             * App Providers
             */
            \App\EventServiceProvider::class,
            \App\Http\RouteServiceProvider::class,
            \App\Campaign\CampaignServiceProvider::class,

            /*
             * Packages
             */
            \BenSampo\Enum\EnumServiceProvider::class,
            \Fruitcake\Cors\CorsServiceProvider::class,
            \Nuwave\Lighthouse\LighthouseServiceProvider::class,
            \Fideloper\Proxy\TrustedProxyServiceProvider::class,
            \NunoMaduro\Collision\Adapters\Laravel\CollisionServiceProvider::class,
        ],

        // Only local
        'local' => [
            \MLL\GraphQLPlayground\GraphQLPlaygroundServiceProvider::class,
        ],

        // Only on console
        'console' => [
            \Laravel\Tinker\TinkerServiceProvider::class,
        ],
    ];
```

---

### Explicit Provider Register

```php
    public function register()
    {
        $this->registerProviders($this->providers['default']);

        if ($this->app->isLocal()) {
            $this->app['config']->set('app.debug', true);

            $this->registerProviders($this->providers['local']);
        }

        if ($this->app->runningInConsole()) {
            $this->registerProviders($this->providers['console']);
        }
    }
```

---

# Do not register aliases

- Creating aliases in `config/app.php` should not be allowed in any project
- Classes must have and respect its namespaces

---

# Explicit Event > Listener Register

- Keep `EventServiceProvider.php` in the root of the project
- Registering events/listeners outside the EventServiceProvider should not be allowed in any project
- This provider should be seen as the *route* of events and is good for newcomers to understand the project

---

# You don't need to be an expert of PSRs or guidelines

### We can just use php-cs-fixer

- The repository must have the `.php_cs` config file and `friendsofphp/php-cs-fixer` dependency
- Run `vendor/bin/php-cs-fixer .` and commit the changes

---

# Questions?

