from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.mail import send_mail, EmailMessage
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Count
from django.views.generic import ListView
from .models import Post, Comment
from .forms import EmailPostForm, CommentForm, SearchForm

#Class based views
class PostListView(ListView):
	queryset = Post.published.all()
	context_object_name = 'posts'
	paginate_by = 3
	template_name = 'main/post/list.html'


#Fucntion based views
def post_list(request):
	object_list = Post.published.all()
	paginator = Paginator(object_list, 3)
	page = request.GET.get('page')
	try:
		posts = paginator.page(page)
	except PageNotAnInteger:
		# If page is not integer deliver the first page
		posts = paginator.page(1)
	except EmptyPage:
	  #If page is out of range deliver last page of results
	  	posts = paginator.page(paginator.num_pages)
	return render(request, 'main/post/list.html', {'page': page,'posts': posts})

def post_detail(request, year, month, day, post):
	post = get_object_or_404(Post, slug=post,
									status='published',
									publish__year=year,
									publish__month=month,
									publish__day=day)

	#List of active comments for this post
	comments = post.comments.filter(active=True)

	new_comment = None

	if request.method == 'POST':
		#A comment was posted
		comment_form = CommentForm(data=request.POST)
		if comment_form.is_valid():
			#Create Comment object but don't save to DB yet
			new_comment = comment_form.save(commit=False)
			#Assign the current post to the comment
			new_comment.post = post
			#Save the comment to the DB
			new_comment.save()
	else:
		comment_form = CommentForm()
	
	# List of similar posts
	post_tags_ids = post.tags.values_list('id', flat=True)
	similar_posts = Post.published.filter(tags__in=post_tags_ids)\
									.exclude(id=post.id)
	similar_posts = similar_posts.annotate(same_tags=Count('tags'))\
									.order_by('-same_tags','-publish')[:4]

	return render(request, 
						'main/post/detail.html',
						{'post': post,
						 'comments': comments,
						 'new_comment': new_comment,
						 'comment_form': comment_form,
						 'similar_posts': similar_posts})

#Send email view
def post_share(request, post_id):
	#Retrieve post by id
	post = get_object_or_404(Post, id=post_id, status='published')
	sent = False
	if request.method == 'POST':
		#Form was submitted
		form = EmailPostForm(request.POST)
		if form.is_valid():
			#Form fields passed validation
			cd = form.cleaned_data
			#... send email
			post_url = request.build_absolute_uri(post.get_absolute_url())
			subject = '{} ({}) recommends you reading {}'.format(cd['name'], cd['email'], post.title)
			message = 'Read "{}" at {}\n\n{}\'s comments:{}'.format(post.title, post_url, cd['name'], cd['comments'])
			email = EmailMessage(subject, message, to=[cd['to']])
			email.send()
			#send_mail(subject, message, 'gitclone0401@gmail.com', [cd['to']])
			sent = True
			
	else:
		form = EmailPostForm()
	return render(request, 'main/post/share.html', {'post': post,
													'form': form,
													'sent': sent})

#Postgres Full text search view
def post_search(request):
	form = SearchForm()
	query = None
	results = []
	if 'query' in request.GET:
		form = SearchForm(request.GET)
		if form.is_valid():
			query = form.cleaned_data['query']
			search_vector = SearchVector('title', weight='A') + 
							SearchVector('body', weight='B')
			search_query = SearchQuery(query)
			results = Post.objects.annotate(
				search=search_vector,
				rank=SearchRank(search_vector, search_query)
				).filter(rank__gte=0.3).order_by('-rank')

	return render(request,
					'main/post/search.html',
					{'form': form,
					 'query': query,
					 'results': results})