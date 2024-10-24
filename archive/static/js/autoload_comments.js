// function getComments(objectid, objectslug){
//   var url = 'object/' + objectid + '/' + objectslug + '/a/comments/';

// }

function fetchAllComments(url, csrf_token) {
  console.log('foo');
  $.ajax({
    url: url,
    headers: {'X-CSRFToken': csrf_token},
    dataType: 'json',
    success: function(data){
      // Based on the status of the response, take the correct action
      if (data.error == true) {
        $('#comment-messages').append('<div class="alert alert-danger" role="alert">' + data.status.name + ' when loading comments: ' + data.status.message + '</div>');
        return false;
      } else {
        $('.comments .comment').remove();
        console.log(data);
        $.each(data['payload'], function(index, comment){
          $('.autoload.comments').append(comment);
        });
      } 
    }
  });
}