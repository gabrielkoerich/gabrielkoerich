slidenumbers: true
build-lists: true

# DevOps in PHP environment

^ Hoje vamos falar sobre:
^ Ambientes semelhantes de 2 empresas diferentes
^ Maneiras diferentes de resolver o mesmo Problema

---

# Who?!

Gabriel Koerich
Over 10 years of experience in PHP and 6 in Laravel
Founder of Bulldesk, responsible for finance and technology

[gabriel@bulldesk.com.br](mailto:gabriel@bulldesk.com.br)
[twitter.com/gabrielmkoerich](https://twitter.com/gabrielmkoerich)
[github.com/gabrielkoerich](https://github.com/gabrielkoerich)

---

![](image/bulldesk.com.br.png)

^ G.

^ O Bulldesk é um software de automação de marketing e CRM, nele é possível criar formulários, landing pages, automações de marketing, e-mail marketing e ter uma visão geral de todas as negociações com seus clientes.

^ Aplicação multi tenant, com uns 1k users por mes

^ Lançamos o bulldesk em março do ano passado e temos uma média de 5M de requests por mês.

---

# Who?!

Evaldo Felipe
Blackops @ Neoway
8 years of SysAdmin
2,5 years of DevOps

[contato@evaldofelipe.com](mailto:contato@evaldofelipe.com)
[twitter.com/evaldofelipe](https://twitter.com/evaldofelipe)

---

![](image/advbox.png)

^ E.

^ Aplicação voltada para o meio juridico, para gestão de processos, organização de tarefas do time, gestão do escritório, atualização automatizada dos processos em atividade (explicar alguns detalhes)

^ Versão free e versão com 9,4k escritorio 15,6k usuários, 5kk atualizacoes/dia com 9.000.000 de requests/mes

---

# Agenda

- PHP Sucks?!
- Workflow
- Infrastructure
- Tools
- Issues and Fixes

^ E.
<!--
- Dev workflow / Source Management
- Continous Integration
- Deploy Platforms
- Monitoring, Security & Optimization
 -->

---

# PHP Sucks?!

^ G.

---

<!-- ![](image/white.png) -->

# PHP Sucks?!

- Easy for beginners
- Easy to "deploy"
- PHP mixed in HTML
- No conventions for function names
- Wordpress

^ G.
^ Pessoal, agora um assunto sério. Todo mundo aqui foi zoado pelo menos uma vez na vida por usar PHP. Que php é lixo, as funções não seguem nenhum padrão e que é realmente muito fácil ver código lixo em php. Mas será que o PHP é tão ruim assim? Na verdade, até a versão 5.2 era muito ruim mesmo. Nem namespace a gente tinha. Até a 5.3 a gente tinha que escrever array LITERALMENTE escrevendo array().

---

> I don't know how to stop it, there was never any intent to write a programming language
-- Rasmus Lerdorf 

---

<!-- ![](image/white.png) -->

# PHP Evolution

|Version|Evolution|
|:---:|---|
|< 5.3 | 💩
|5.3   | Namespaces, closures
|5.4   | Traits, [] for arrays
|5.5   | OPCache, finally on try blocks
|5.6   | Argument unpacking (...$args)
|~~6.0~~ | 👋🏻
|7.0   | Performance (thanks to HHVM), return and scalar types, improved exceptions
|7.1   | Nullable types (?int), catch multiple exceptions

^ G.
^ A OO do PHP foi totalmente reescrita na versão 5.
^ A verdade é que o PHP é muito simples e deixa fazer o que você quiser. Quem tem que ser bom é você. Quem tem que usar os padrões é você. Com o laravel é a mesma coisa, ele te deixa fazer um MONTE de merda. Eu já vi código em Laravel pior que código em Wordpress.
^ Mas sério, muita coisa mudou de lá pra cá, e a partir da versão 7 eu finalmente acho que os desenvolvedores PHP serão cada vez mais respeitados/valorizados.

---

> I have absolutely no idea how to write a programming language, I just kept adding the next logical step on the way.
-- Rasmus Lerdorf 

---

# Community Evolution

Autoloaders, Composer & Packagist
Frameworks (Zend, Symfony, Laravel)
PHP FIG and PSRs

**Standards**
PSR-1: Basic Coding
PSR-2: Coding Style Guide
PSR-3: Logger Interface
PSR-4: Autoloader
PSR-5: Caching Interface
PSR-7: HTTP Message Interface

---

# Modern PHP

```php
/**
 * Create a new instance.
 */
public function __construct(AutomationRepository $automations)
{
    $this->automations = $automations;
}

/**
 * @Get("automation", as="automation.index")
 */
public function index(Request $request): Response
{
    if ($request->expectsJson())) {
        return $this->automations->getActive()->pluck('name', 'id');
    }

    $automations = $this->automations->categorized($request->input('categories'))
        ->orderBy('name')
        ->paginate(50);

    return new Response(view('pages.automation.index')->with(compact('automations')), 200);
}
```

^ G.

---

# Laravel Features

- Routes & Controllers
- Service Container & Dependency Injection
- Migrations & ORM
- Artisan command line
- Queues (beanstalkd, redis, amazon sqs)
- Broadcasting (Pusher or socket.io)
- Mix for webpack

^ G.
^ Falar que usamos laravel e estas são as features

---

# Development Workflow & <br>Source Management

---

# Development Workflow & Source Management

- People
- Workflow
- Rules, code patterns, PSRs
- Local environment
- ~~Database dump~~ Migrations / Seeds

^ G.

^ Um projeto é feito por pessoas, por isso os indivíduos e suas interações são a parte mais importante de todo o desenvolvimento de software. Claro que não podemos esquecer dos processos, são eles que nos fazem continuar no caminho certo, mas as pessoas sempre vêm em primeiro lugar.

^ Nós vamos falar também sobre as diretrizes de desenvolvimento, como cada dev deve se portar ao desenvolver e comitar códigos novos para sua aplicação.

^ Como configurar seu ambiente local, o modo como vão instalar o repositório e rodar todos os migrations e seeds. Nenhum dev deve receber o dump de seu banco de dados de produção. Uma dica interessante é ao criar um novo model/migration, criar também um factory e um novo seed.

^ Tudo isso deve estar bem definido para qualquer dev novo entrar e não perder muito tempo configurando o projeto em sua máquina.

---

# Github Flow

- Anything in master is deployable
- Every new branch should be created off of master
- Branches must have descriptive names (create-cache-manager, improve-auth, refactor-acl)
- Pull requests must be reviewed by at least 2 people
- When ready, you should merge and deploy immediately

^ E.

---

# Github Flow

![inline](image/github-flow.png)

---

# Bulldesk Guidelines

![inline](image/bulldesk-guidelines.png)

---

![inline](image/coding-style.png)

---

# Local Environment

---

# Laravel Valet

```bash
# Install PHP/Composer/MySQL/Redis local

# On MacOS
$ composer global require laravel/valet

# On Linux
$ composer global require cpriego/valet-linux

$ valet install

$ cd ~/Projects && valet park

# All directories in ~/Projects will be acessible at http://{folder}.test
```

^ E.
^ Falar da evolução do ambiente local
^ engineX

---

# Vessel (Docker)

##PHP 7.2, MySQL 5.7, Redis & NodeJS with NPM, Yarn & Gulp

```bash
# Install docker

$ composer require shipping-docker/vessel

# Register Vessel\VesselServiceProvide if not on Laravel 5.5

$ php artisan vendor:publish --provider="Vessel\VesselServiceProvider"

$ bash vessel init

$ ./vessel start

# Acessible at http://localhost
```

^ E.
^ Esse cara que fez o Vessel é o fideloper...

---

# Continuous Integration

^ G.

---

# Continuous Integration

- Tests
- Code coverage
- Code quality

^ G.
^ Falar sobre Travis CI, Clode Climate, Scrutinizer
^ Explicar sobre testes automatizados, cobertura de testes, qualidade de código, integração contínua e mostrar as ferramentas que podem ser utilizadas para ver qualidade, coverage e rodar os testes.

---

![](image/travis-build.png)

---

![inline](image/travis-slack.png)

---

![](image/code-climate.png)

---

# Production/QA Environment


^ E.
^ Falar sobre Forge, Envoyer, Let's Encrypt
^ Mostrar como funciona o provisionamento de máquinas para produção no Forge (sem xdebug, com opcache) e a integração com deploy contínuo com zero downtime no Envoyer, citando que é possível criar vários servidores em rede, cada um fazendo o seu papel para escalar a aplicação.

---

# Provision/Deploy

- Multi Servers / Instances
- Continuous Deploy
- Zero downtime
- Database Replication
- PHP 7.2
- SSL & http2

^ E.

---

![](image/forge.png)

^ E 
Infrastructure automation as a Service
^ PHP environment as a Service

---

![](image/forge-features.png)

---

![](image/forge-new-server.png)

---

# Recipes

![inline](image/forge-provision-hooks.png)

---

![](image/forge-network.png)

---

# Firewall Rules

```bash
ACCEPT     tcp  --  10.132.103.204       anywhere             tcp dpt:mysql
ACCEPT     udp  --  10.132.103.204       anywhere             udp dpt:mysql
ACCEPT     tcp  --  10.132.103.204       anywhere             tcp dpt:postgresql
ACCEPT     udp  --  10.132.103.204       anywhere             udp dpt:postgresql
ACCEPT     tcp  --  10.132.103.204       anywhere             tcp dpt:11211
ACCEPT     udp  --  10.132.103.204       anywhere             udp dpt:11211
ACCEPT     tcp  --  10.132.103.204       anywhere             tcp dpt:6379
ACCEPT     udp  --  10.132.103.204       anywhere             udp dpt:6379
ACCEPT     tcp  --  10.132.103.204       anywhere             tcp dpt:11300
ACCEPT     udp  --  10.132.103.204       anywhere             udp dpt:11300
```

^ E 
Portas liberadas 80, 22 e 443
22 pode ser trocada

---

![](image/forge-load-balancer.png)

---

![](image/forge-balanced-servers.png)

---

# Beanstalkd queues + Supervisor

![inline](image/forge-workers.png)

^ G.

---

![](image/beanstalkd-console.png)

---

## Issue

## Laravel doesn't understand that the request came from a client and not from the load balancer


^ G.

---

# Trusted Proxy

```bash
$ composer require fideloper/proxy

# Register Fideloper\Proxy\TrustedProxyServiceProvider

$ php artisan vendor:publish --provider="Fideloper\Proxy\TrustedProxyServiceProvider"
```

```php
// Http/Kernel.php
protected $middleware = [
    //...
    \Fideloper\Proxy\TrustProxies::class,
];

// config/trustedproxy.php
return [
    'proxies' => [
        '192.168.10.10', // Load balancer's IP address
    ],
//...
```

---

## Issue

## How to serve some files from a single server?

---

^ G.
^ Falar sobre Websocket node e redis

# Nginx Websocket Proxy

```bash

upstream websocket {
    least_conn;
    server 10.xx.xx.xx:2095; #websocket server ip
}

location /socket.io {
    proxy_pass http://websocket;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;

    proxy_connect_timeout       300;
    proxy_send_timeout          300;
    proxy_read_timeout          300;
    send_timeout                300;
}
```
---

# Database Replication

^ E. 

---

# Master/Slave Config

```php
//...
'connections' => [

    'mysql' => [
        'write' => [
            'host' => env('DB_WRITE_HOST', env('DB_HOST', '127.0.0.1')),
        ],

        'read' => [
            'host' => [
                env('DB_WRITE_HOST', env('DB_HOST', '127.0.0.1')),
                env('DB_READ_HOST', env('DB_HOST', '127.0.0.1')),
            ],
        ],

        'backup' => [
            'host' => env('DB_BACKUP_HOST', env('DB_READ_HOST', '127.0.0.1')),
            'arguments' => '--single-transaction --skip-tz-utc',
        ],
    //...
];
```

^

---

![](image/envoyer.png)

^ E.

---

![inline](image/envoyer-add-server.png)

---

![inline](image/envoyer-ssh.png)

---

![inline](image/envoyer-hooks.png)

---

# .env

```
REDIS_HOST=
BEANSTALKD_HOST=

DB_HOST=
DB_WRITE_HOST=
DB_READ_HOST=
DB_BACKUP_HOST=

DB_NAME=
DB_USER=
DB_PASSWORD=

CACHE_DRIVER=redis
SESSION_DRIVER=redis
```

---

![inline](image/envoyer-server-trick.png)

---

![](image/envoyer-phpunit.png)

---

![](image/envoyer-frontend.png)

---

![](image/envoyer-migrations-hook.png)

---

![](image/envoyer-restart.png)

---

![](image/envoyer-bugsnag.png)

---

#Monitoring, Security & Optimization

---

#Monitoring, Security & Optimization

- CDN
- Monitors
- Logs e exceptions centralized
- Backups
- Load tests

^ Falar sobre Cloudflare, Papertrail, Bugsnag, Newrelic, backup jobs and loader.io, beanstalkd console
^ Explicar que os logs devem ser centralizados no mesmo serviço, já que eles vêm de várias máquinas diferentes. Dizer que é interessante logar tudo o que acontece no app para facilitar o debug. Falar sobre o monitoramento via Newrelic, logs via Papertrail e exceptions centralizadas no Bugsgnag. Testes de carga no loader.io

---

![](image/cf.png)

---

![inline](image/cf-overview.png)

---

^ E.
^ mesma issue do load balancer

```php
/**
 * Set the CloudFlare conneting IP and https if applied.
 *
 * @param  \Illuminate\Http\Request $request
 * @param  \Closure                 $next
 * @return mixed
 */
public function handle($request, Closure $next)
{
    if (! app()->environment('production')) {
        return $next($request);
    }

    if ($request->server->has('HTTP_CF_CONNECTING_IP')) {
        if ($request->isSecure()) {
            $request->server->set('HTTPS', true);
        }

        $request->server->set('REMOTE_ADDR', $request->server->get('HTTP_CF_CONNECTING_IP'));

        return $next($request);
    }

    logf('CF: Blocked request to %s from %s', [$request->fullUrl(), $request->ip()]);

    return new Response('', 404);
}
```

---

![](image/cf-page-rules.png)

---

## Issue
## How to clear this cache automatically?

^ G.

---

```php
/**
 * Get the path to a versioned asset file.
 *
 * @param  string $asset
 * @return string
 */
function versioned($asset)
{
    static $production, $base, $deploy, $sha;

    $production = app()->environment('production');

    if (is_null($base)) {
        $base = $production ? 'https://static.bulldesk.com.br/' : '/';
    }

    if ($production === false) {
        return $base.$asset . '?v=' . str_random(3);
    }

    if (is_null($deploy)) {
        $deploy = public_path('build/deploy');
    }

    if (is_null($sha) && file_exists($deploy)) {
        $sha = file_get_contents($deploy);
    }

    if (! empty($sha)) {
        return $base.$asset . '?v='.$sha;
    }

    return $base.$asset;
}

<script src="{{ versioned('build/scripts/app.js') }}"></script> //https://static.bulldesk.com.br/build/scripts/app.js?v=fbe06e04c4f8ddd1c94c63f3a001807bace679e0

```

^ G.
^ E. Eu utilizo dentro do deploy do envoyer via API com token

---

# Monitoring

---

![](image/newrelic.png)

^ G.

---

![inline](image/datadog.png)

^ E.

---

![inline](image/datadog-notification.png)

---

![inline](image/lets-monitor.png)

^ E.

---

![](image/loader-io.png)

^ E.

---

## Issue
## How to centralize logs and exceptions?

^ G.

---

![](image/papertrail.png)

---

![](image/papertrail-logs.png)

---

```php
// LogServiceProvider.php

/**
 * The papertrail log format.
 *
 * @var string
 */
protected $papertrailFormat = '%channel%.%level_name%: %message% %extra%';

/**
 * Configure the application's logging facilities.
 *
 * @return void
 */
public function boot()
{
    if ($this->app->environment('production', 'staging')) {
        $syslog = new \Monolog\Handler\SyslogHandler('laravel');
        $formatter = new \Monolog\Formatter\LineFormatter($this->papertrailFormat);

        $syslog->setFormatter($formatter);

        $this->app['log']->getMonolog()->pushHandler($syslog);
    }
}
```

---

![](image/forge-recipe.png)

^ G.

---

![](image/bugsnag.png)

^ G.

---

![inline](image/bugsnag-slack.png)

^ G.

---

![](image/bugsnag-errors.png)

---
<!-- --- -->

<!-- ![original](image/white.png) -->

![inline](image/bugsnag-notification.png)

<!-- ^ G. -->

---

# Backups

```bash
$ composer require backup-manager/backup-manager

# OR
$ composer require backup-manager/laravel

# OR
$ composer require spatie/laravel-backup
```

^ G.
^ Na época instalei o backup-manager e não queria ficar refém de um package laravel por causa das atualizações / precisava de umas opções a mais para o backup do innoDB. Mas hoje acho que o melhor e mais configurável é o laravel-backup
^ E. uso bash.sh coloco senha no arquivo e mando pro S3

---

```php
(...)

/**
 * Execute the backup command.
 *
 * @return void
 */
public function handle()
{
    $database = $this->option('database') ?: 'mysql';
    $destination = $this->option('destination') ?: 's3';
    $destinationPath = 'dump_'. (new Carbon)->format('Y_m_d_H_i_s').'.sql';
    $compression = 'gzip';

    $this->info('Dumping database and uploading...');

    $destinations = [new Destination($destination, $destinationPath)];

    $this->backupProcedure->run($database, $destinations, $compression);

    $completePath = 'database/' . $destinationPath;

    $this->info(sprintf('Successfully dumped %s, compressed with %s and store it to %s at %s',
        $database,
        $compression,
        $destination,
        $completePath
    ));

    $last = new Carbon('last day of this month');

    // Delete file in 10 days if this not the last
    if ((new Carbon)->isSameAs('d/m/Y', $last)) {
        $this->info('Scheduled job to delete the backup file ' . $completePath . ' in 10 days.');

        dispatch((new DeleteFile($completePath . '.gz', 's3_backup'))->delay(24 * 60 * 60 * 10));
    }
}
```

---

# Then

![inline](image/topology-old.png)

---

# Now

![inline](image/topology.png)

---

# Lessons Learned

---

# 1. Don't optimize or escale prematurely, but be prepared for this.

^ E.

---

# 2. Time is money.

^ G.

---

# 3. Use microservices only if you can maintain them.

^ E.

---

# 4. Study/learn and enjoy everything the internet gives you for free.

^ G.

---

![](image/github-education.png)

---

![original](image/white.png)

![inline](image/logo-github.png) ![inline](image/logo-datadog.png)

![inline](image/logo-digitalocean.png) ![inline](image/logo-gitkraken.png)

![inline](image/logo-namecheap.png) ![inline](image/logo-sendgrid.png)

![inline](image/logo-stripe.png) ![inline](image/logo-travis-ci.png)

---

# Thanks!

---

# We're hiring!

<br>
# Questions?

<br>
[bulldesk.com.br](bulldesk.com.br)
[gabriel@bulldesk.com.br](mailto:gabriel@bulldesk.com.br)
[twitter.com/gabrielmkoerich](https://twitter.com/gabrielmkoerich)

---

# Ref

<br>[en.wikiquote.org/wiki/Rasmus_Lerdorf](https://en.wikiquote.org/wiki/Rasmus_Lerdorf)
<br>[guides.github.com/introduction/flow](https://guides.github.com/introduction/flow)
<br>[github.com/gabrielkoerich/guidelines](https://github.com/gabrielkoerich/guidelines)
<br>[vessel.shippingdocker.com](vessel.shippingdocker.com)
<br>[docs.spatie.be/laravel-backup](https://docs.spatie.be/laravel-backup)
<br>[gabrielkoerich.com/talks/infra](https://gabrielkoerich.com/talks/infra)
<br>[php-fig.org](https://php-fig.org)