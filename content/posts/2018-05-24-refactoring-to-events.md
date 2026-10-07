+++
title = "Refactoring to Events"
date = 2018-05-24
[taxonomies]
tags = ["event-driven", "architecture", "laravel", "software-engineering", "medium"]
[extra]
source = "medium"
original_url = "https://gabrielkoerich.medium.com/refactoring-to-events-72cba6873d9c"
+++

I know, we're all used to seeing that kind of messy code with a lot of `ifs` and `elses`, right?

But today we're going to try to change this a little bit.

Well, let's start with a sample. It's a class that handles Stripe webhooks.

```ts
class WebhookController extends Controller
{
    public function handleWebhook(Request $request)
    {
        $payload = json_decode($request->getContent(), true);
        if (! $this->isInTestingEnvironment() && ! $this->eventExistsOnStripe($payload['id'])) {
            return;
        }

        $method = 'handle'.studly_case(str_replace('.', '_', $payload['type']));

        if (method_exists($this, $method)) {
            return $this->{$method}($payload);
        } else {
            return $this->missingMethod();
        }
    }

    protected function handleCustomerSubscriptionDeleted(array $payload)
    {
        $user = $this->getUserByStripeId($payload['data']['object']['customer']);

        if ($user) {
            $user->subscriptions->filter(function ($subscription) use ($payload) {
                return $subscription->stripe_id === $payload['data']['object']['id'];
            })->each(function ($subscription) {
                $subscription->markAsCancelled();
            });
        }

        return new Response('Webhook Handled', 200);
    }
```

*No, you would never in your entire life guess that I got this code from the [Cashier repository](https://raw.githubusercontent.com/laravel/cashier/7.0/src/Http/Controllers/WebhookController.php). Never.*

That's fine, right? If we receive an event called `customer.subscription.deleted`, our method `handleCustomerSubscriptionDeleted` will handle it!

But that's only fine while your application is starting and you don't need to handle much. What if we need to receive **all** Stripe methods? Should we take the same approach?

Nope!

We have better ways to handle that, thanks to [Laravel Events](https://laravel.com/docs/5.6/events).

All we need to do to write more consistent and understandable code is to create an event for every hook that we want to receive.

So if you need to listen to Stripe's customer subscription deleted hook, you create an event called `StripeCustomerSubscriptionDeleted`, and then create the listeners that handle that event.

This makes our controller thinner, because it moves responsibilities to event listeners:

```ts
class WebhookController extends Controller
{
    public function handleWebhook(Request $request)
    {
        $payload = json_decode($request->getContent(), true);
        if (! $this->isInTestingEnvironment() && ! $this->eventExistsOnStripe($payload['id'])) {
            return;
        }

        $class = '\App\Event\Stripe' . studly_case(str_replace('.', '_', $payload['type']));
        
        if (class_exists($class)) {
            return new $class($payload);
        } 

        return $this->missingMethod();
    }
}
```

Now, for every event that Stripe sends us, the controller will try to call an event. We just need to create and handle it.

Then we create our event:

```ts
class StripeCustomerSubscriptionDeleted
{
    /**
     * Create a new instance.
     */
    public function __construct(array $payload)
    {
        $this->payload = $payload;
    }

    public function getCustomer()
    {
        // Get the current customer based on $payload
    }
}
```

And our listener:

```ts
final class StripeCancelSubscription
{
    /**
     * Handle the event.
     */
    public function handle(StripeCustomerSubscriptionDeleted $event)
    {
        $customer = $event->getCustomer();

        $customer->subscriptions->filter(function ($subscription) use ($event) {
            return $subscription->stripe_id === $event->payload['data']['object']['id'];
        })->each(function ($subscription) {
            $subscription->markAsCancelled();
        });
    }
}
```

Now that we have our event and listener, we need to tell Laravel how to handle them. To do this, we just add them to the EventServiceProvider:

```ts
class EventServiceProvider extends ServiceProvider
{
    /**
     * The event listener mappings for the application.
     */
    protected $listen = [
        /*
         * Stripe Billing Events
         */
        \App\Event\StripeCustomerSubscriptionDeleted::class => [
            \App\EventListener\StripeCancelSubscription:class
        ],
```

And that's it!

You can apply this in countless situations where you're handling a lot of conditions.

Just create events and separate your handlers. Your code will be cleaner and easier to understand. And you can also run some of those listeners in queues, so your users don't need to wait for a response that takes a long time to return.

**Of course**, my example only explains one situation. I really think this should only be applied if you have a lot of events and listeners to handle in your workflow. Otherwise, just keep the default approach.

*Originally published on [Medium](https://gabrielkoerich.medium.com/refactoring-to-events-72cba6873d9c)*
