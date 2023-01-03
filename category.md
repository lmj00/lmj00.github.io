---
layout: default
---

{% assign category = 'Git' | default: page.title %}

<h2>
  <a href="/category/git">
    {{ category }}
    ({{ site.categories[category].size }})
  </a>
</h2>

<ul class="posts-list">
  {% for post in site.categories[category] limit:5 %}
    <li>
      <h3>
        <a href="{{ site.baseurl }}{{ post.url }}">
          {{ post.title }}
        </a>
        <small>{{ post.date | date:"%Y-%m-%d" }}</small>
      </h3>
    </li>
  {% endfor %}
</ul>

<br>

{% assign category = 'Django' | default: page.title %}

<h2>
  <a href="/category/django">
    {{ category }}
    ({{ site.categories[category].size }})
  </a>
</h2>

<ul class="posts-list">
  {% for post in site.categories[category] limit:5 %}
      <li>
        <h3>
          <a href="{{ site.baseurl }}{{ post.url }}">
            {{ post.title }}
          </a>
          <small>{{ post.date | date:"%Y-%m-%d" }}</small>
        </h3>
      </li>
  {% endfor %}
</ul>

<br>

{% assign category = 'Spring' | default: page.title %}

<h2>
  <a href="/category/spring">
    {{ category }}
    ({{ site.categories[category].size }})
  </a>
</h2>

<ul class="posts-list">
  {% for post in site.categories[category] limit:5 %}
    <li>  
      <h3>
        <a href="{{ site.baseurl }}{{ post.url }}">
          {{ post.title }}
        </a>
        <small>{{ post.date | date:"%Y-%m-%d" }}</small>
      </h3>
    </li>
  {% endfor %}
</ul>