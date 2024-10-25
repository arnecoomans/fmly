function fetchAllComments(url, csrf_token) {
  console.log('Fetching all comments on ' + url);
  $.ajax({
    url: url,
    headers: {'X-CSRFToken': csrf_token},
    dataType: 'json',
    success: function(data){
      console.log(data);
      // Based on the status of the response, take the correct action
      if (data.error == true) {
        $('#comment-messages').append('<div class="alert alert-danger" role="alert">' + data.status.name + ' when loading comments: ' + data.status.message + '</div>');
        return false;
      } else {
        $('.comments li').remove();
        $.each(data['payload'], function(index, comment){
          $('.autoload.comments').append(comment);
        });
      } 
    }
  });
}

function fetchCommentForm(url, csrf_token) {
  console.log('Fetching comment form');
  $.ajax({
    url: url,
    headers: {'X-CSRFToken': csrf_token},
    dataType: 'json',
    success: function(data){
      // console.log(data);
      // Based on the status of the response, take the correct action
      if (data.error != true) {
        $('.comment-form').append(data['payload']);
      } 
    }
  });
}

$(document).on('click', '#commentsubmit', function() {
  const url = $(this).data('url');  // Get the data-url attribute
  const csrf_token = $('#csrf_token').data('csrf');  // Get the data-csrf attribute
  const comment = $('#commentcontent').val();  // Get the value of the comment field
  const allcommentsurl = $(this).data('all-comments-url');

  console.log('Submitting ' + comment + ' to ' + url);
  $.ajax({
    url: url,
    type: 'POST',
    data: {'comment': comment},
    headers: {'X-CSRFToken': csrf_token},
    dataType: 'json',
    success: function(data){
      // Based on the status of the response, take the correct action
      if (data.error == true) {
        $('#comment-messages').append('<div class="alert alert-danger" role="alert">' + data.message + '.</div>');
        return false;
      } else {
        console.log(data);
        $('#comment-messages').append('<div class="alert alert-success" role="alert">Comment submitted successfully</div>');
        fetchAllComments(allcommentsurl, csrf_token);
        $('#commentcontent').val('');
      } 
    }
  });
});